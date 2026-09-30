"""Reference third-party edge: connects ANY recognition program to the platform.

It does not use the platform's edge-agent. It shows the whole contract with plain JSON:

  1. PUT  /api/v1/edge/cameras/{code}        announce a camera -> get its stream path
  2. MQTT edge/{device}/heartbeat             every 10 s   (device online, CPU/memory)
     MQTT edge/{device}/status                retained, also the Last Will ("offline")
     MQTT edge/{device}/cameras/{cam}/status  camera / AI / stream health
  3. RTSP push  <media>/<stream_path>         annotated H.264 video (user = device ID, password = device key)
  4. MQTT edge/{device}/cameras/{cam}/logs    whatever was recognised; same event_id again = update
     POST /api/v1/edge/snapshots/presign      optional snapshot upload (HTTP PUT to the returned URL)

Replace `fake_recognition()` and the FFmpeg test pattern with your own AI output.
Only dependency: paho-mqtt >= 2 (and an ffmpeg binary for the video part).

    EDGE_API_URL=http://<platform>:8000/api/v1 EDGE_DEVICE_ID=REACH01 EDGE_DEVICE_KEY=... \
    EDGE_MQTT_USERNAME=edge EDGE_MQTT_PASSWORD=... python generic_edge.py
"""

from __future__ import annotations

import json
import logging
import os
import random
import signal
import socket
import subprocess
import threading
import time
import urllib.request
import uuid
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

import paho.mqtt.client as mqtt

log = logging.getLogger("generic-edge")

API = os.environ.get("EDGE_API_URL", "http://localhost:8000/api/v1").rstrip("/")
DEVICE = os.environ["EDGE_DEVICE_ID"]
KEY = os.environ["EDGE_DEVICE_KEY"]
MQTT_USER = os.environ.get("EDGE_MQTT_USERNAME")
MQTT_PASS = os.environ.get("EDGE_MQTT_PASSWORD")
# overrides for when the addresses in /edge/config are not reachable from here (e.g. inside Docker)
MQTT_HOST = os.environ.get("EDGE_MQTT_HOST")
MQTT_PORT = os.environ.get("EDGE_MQTT_PORT")
RTSP_PUBLISH_URL = os.environ.get("EDGE_RTSP_PUBLISH_URL")
CAMERAS = [c for c in os.environ.get("EDGE_CAMERAS", "cam01:Demo camera").split(",") if c]
WIDTH, HEIGHT, FPS = 1280, 720, 15


def now() -> str:
    return datetime.now(UTC).isoformat()


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Device-Key": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read() or b"{}")


def upload_snapshot(camera_code: str, jpeg: bytes) -> str | None:
    try:
        presign = api("POST", "/edge/snapshots/presign", {"camera_code": camera_code})
        req = urllib.request.Request(presign["upload_url"], method="PUT", data=jpeg,
                                     headers={"Content-Type": "image/jpeg"})
        urllib.request.urlopen(req, timeout=10).close()
        return presign["object_key"]
    except Exception as exc:  # a missing snapshot never blocks the log itself
        log.warning("snapshot upload failed: %s", exc)
        return None


def grab_test_jpeg() -> bytes:
    """Stand-in for 'the frame your AI just looked at'."""
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}",
         "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
        check=True, capture_output=True,
    ).stdout


class VideoPusher(threading.Thread):
    """Annotated video -> H.264 -> RTSP push. Replace the lavfi input with your rendered frames
    (e.g. `-f rawvideo -pix_fmt bgr24 -s WxH -r FPS -i -` and write OpenCV frames to stdin)."""

    def __init__(self, target: str) -> None:
        super().__init__(daemon=True)
        self.target = target
        self.proc: subprocess.Popen | None = None
        self.stopped = threading.Event()

    def run(self) -> None:
        delay = 1
        while not self.stopped.is_set():
            box = "drawbox=x='200+100*sin(t)':y=200:w=240:h=320:color=cyan@0.9:t=4"
            self.proc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-nostdin", "-re", "-f", "lavfi",
                 "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={FPS}", "-vf", box, "-an",
                 "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
                 "-g", str(FPS * 2), "-b:v", "1M", "-f", "rtsp", "-rtsp_transport", "tcp", self.target],
            )
            started = time.monotonic()
            self.proc.wait()
            if self.stopped.is_set():
                return
            delay = 1 if time.monotonic() - started > 30 else min(delay * 2, 30)
            log.warning("video push ended (code %s); retrying in %ss", self.proc.returncode, delay)
            self.stopped.wait(delay)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        self.stopped.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def fake_recognition(camera: str) -> list[dict]:
    """Your AI goes here. Return any number of logs; the platform stores them as-is."""
    x = random.randint(0, WIDTH - 300)
    return [{
        "event_type": random.choice(["demo.person", "demo.helmet_missing", "demo.zone_intrusion"]),
        "severity": random.choice(["info", "info", "warning", "critical"]),
        "message": f"something recognised on {camera}",
        "data": {"zone": random.choice(["A", "B"]), "score": round(random.random(), 2)},
        "detections": [{"class_id": 0, "class_name": "person", "confidence": 0.87,
                        "bbox": {"x1": x, "y1": 180, "x2": x + 240, "y2": 540}}],
        "frame": {"width": WIDTH, "height": HEIGHT},
    }]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # 1. announce cameras -> stream paths
    cams: dict[str, dict] = {}
    for item in CAMERAS:
        code, _, name = item.partition(":")
        cams[code] = api("PUT", f"/edge/cameras/{code}", {"name": name or code})
        log.info("camera %s -> %s", code, cams[code]["stream_path"])
    config = api("GET", "/edge/config")

    # 2. MQTT with a Last Will so the platform sees us go offline
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE}-{uuid.uuid4().hex[:6]}")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    status_topic = f"edge/{DEVICE}/status"
    client.will_set(status_topic, json.dumps({"device_uuid": DEVICE, "state": "offline"}), qos=1, retain=True)
    client.on_connect = lambda c, *_: c.publish(
        status_topic, json.dumps({"device_uuid": DEVICE, "state": "online", "timestamp": now()}), qos=1, retain=True
    )
    client.connect(MQTT_HOST or config["mqtt"]["host"], int(MQTT_PORT or config["mqtt"]["port"]))
    client.loop_start()

    # 3. video: rtsp://<device>:<key>@media:8554/<stream_path>
    base = urlsplit(RTSP_PUBLISH_URL or config["streaming"]["rtsp_publish_url"])
    pushers = {}
    for code, cam in cams.items():
        target = f"rtsp://{quote(DEVICE, safe='')}:{quote(KEY, safe='')}@{base.netloc}/{cam['stream_path']}"
        pushers[code] = VideoPusher(target)
        pushers[code].start()

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    open_events: list[tuple[float, str, str]] = []  # (close_at, camera, event_id)
    tick = 0
    while not stop.wait(1):
        tick += 1
        if tick % 10 == 0:
            load = os.getloadavg()[0] / (os.cpu_count() or 1) * 100
            client.publish(f"edge/{DEVICE}/heartbeat", json.dumps({
                "device_uuid": DEVICE, "timestamp": now(), "cpu_usage": min(100.0, round(load, 1)),
                "memory_usage": 0, "agent_version": "generic-edge/1.0", "hostname": socket.gethostname(),
            }), qos=0)
        if tick % 5 == 0:
            for code, pusher in pushers.items():
                client.publish(f"edge/{DEVICE}/cameras/{code}/status", json.dumps({
                    "camera_id": code, "timestamp": now(), "rtsp_status": "online", "ai_status": "running",
                    "stream_status": "streaming" if pusher.alive else "connecting",
                    "input_fps": FPS, "inference_fps": 5, "output_fps": FPS if pusher.alive else 0,
                    "resolution": f"{WIDTH}x{HEIGHT}", "last_frame_at": now(),
                }), qos=0)
        if tick % 7 == 0:
            for code in cams:
                for entry in fake_recognition(code):
                    entry.update(event_id=uuid.uuid4().hex, device_id=DEVICE, camera_id=code, timestamp=now(),
                                 snapshot_key=upload_snapshot(code, grab_test_jpeg()))
                    client.publish(f"edge/{DEVICE}/cameras/{code}/logs", json.dumps(entry), qos=1)
        if tick % 20 == 0:
            # a lifecycle event: opened now, updated (same event_id) a few seconds later
            code = random.choice(list(cams))
            event_id = f"leave-{uuid.uuid4().hex[:12]}"
            client.publish(f"edge/{DEVICE}/cameras/{code}/logs", json.dumps({
                "event_id": event_id, "device_id": DEVICE, "camera_id": code, "timestamp": now(),
                "event_type": "office.leave", "severity": "warning", "status": "open",
                "message": "S01 left the seat", "data": {"seat_id": "S01", "leave_time": now()},
            }), qos=1)
            open_events.append((time.monotonic() + 8, code, event_id))
        for item in [e for e in open_events if e[0] <= time.monotonic()]:
            open_events.remove(item)
            _, code, event_id = item
            client.publish(f"edge/{DEVICE}/cameras/{code}/logs", json.dumps({
                "event_id": event_id, "device_id": DEVICE, "camera_id": code, "event_type": "office.leave",
                "severity": "info", "status": "returned", "message": "S01 back at the seat",
                "data": {"return_time": now(), "away_seconds": 8},
            }), qos=1)

    for pusher in pushers.values():
        pusher.stop()
    client.publish(status_topic, json.dumps({"device_uuid": DEVICE, "state": "offline", "timestamp": now()}),
                   qos=1, retain=True).wait_for_publish(3)
    client.loop_stop()


if __name__ == "__main__":
    main()
