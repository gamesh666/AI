"""Reference third-party edge: connects ANY recognition program to the platform.

It does not use the platform's edge-agent. It shows the whole contract with plain JSON:

  1. PUT  /api/v1/edge/cameras                 the COMPLETE camera list -> stream paths (cameras no longer
                                                listed are disabled on the platform, not deleted)
  2. POST /api/v1/edge/heartbeat                every 10 s (device online, CPU/memory, models); the answer
                                                carries pending commands and the config version
     POST /api/v1/edge/cameras/{cam}/status     camera / AI / stream health
     POST /api/v1/edge/status                   {"state": "offline"} on shutdown
  3. RTSP push  <media>/<stream_path>           annotated H.264 video (user = device ID, password = device key)
  4. POST /api/v1/edge/logs                     whatever was recognised; same event_id again = update
     POST /api/v1/edge/snapshots/presign        optional snapshot upload (HTTP PUT to the returned URL)

Everything authenticates with the device's own key (X-Device-Key). EDGE_TELEMETRY=mqtt sends step 2 and 4
over the shared MQTT account instead (legacy; needs paho-mqtt >= 2 and EDGE_MQTT_USERNAME / _PASSWORD).

Replace `fake_recognition()` and the FFmpeg test pattern with your own AI output.
No dependencies besides the Python standard library and an ffmpeg binary for the video part.

    EDGE_API_URL=http://<platform>:8000/api/v1 EDGE_DEVICE_ID=REACH01 EDGE_DEVICE_KEY=... python generic_edge.py
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
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit

log = logging.getLogger("generic-edge")

API = os.environ.get("EDGE_API_URL", "http://localhost:8000/api/v1").rstrip("/")
DEVICE = os.environ["EDGE_DEVICE_ID"]
KEY = os.environ["EDGE_DEVICE_KEY"]
TELEMETRY = os.environ.get("EDGE_TELEMETRY", "http")  # http | mqtt (legacy)
# override for when the address in /edge/config is not reachable from here (e.g. inside Docker)
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


class HttpTelemetry:
    """Heartbeat / status / logs over HTTPS with the device key."""

    def __init__(self, on_config_changed) -> None:
        self.config_version: int | None = None
        self.on_config_changed = on_config_changed

    def _post(self, path: str, body: dict | list) -> dict:
        try:
            return api("POST", path, body)
        except HTTPError as exc:  # 4xx: the platform says why in {"detail": ...}; do not resend as-is
            log.warning("%s refused (%s): %s", path, exc.code, exc.read()[:300].decode(errors="replace"))
        except (URLError, TimeoutError) as exc:  # platform unreachable: a real edge would queue and retry
            log.warning("%s failed: %s", path, exc)
        return {}

    def heartbeat(self, hb: dict) -> None:
        ack = self._post("/edge/heartbeat", hb)
        for cmd in ack.get("commands", []):
            log.info("command from the platform: %s %s", cmd["command"], cmd.get("params"))
            if cmd["command"] == "reload_config":
                self.on_config_changed()
        version = ack.get("config_version")
        if version is not None and self.config_version is not None and version != self.config_version:
            self.on_config_changed()
        if version is not None:
            self.config_version = version

    def status(self, state: str) -> None:
        self._post("/edge/status", {"state": state, "timestamp": now()})

    def camera_status(self, code: str, status: dict) -> None:
        self._post(f"/edge/cameras/{code}/status", status)

    def log(self, entry: dict) -> None:
        self._post("/edge/logs", entry)  # also takes a list of up to 100 logs

    def close(self) -> None:
        self.status("offline")


class MqttTelemetry:
    """Legacy: the same payloads over the shared MQTT account (with a Last Will for "offline")."""

    def __init__(self, config: dict) -> None:
        import paho.mqtt.client as mqtt

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE}-{uuid.uuid4().hex[:6]}")
        user = os.environ.get("EDGE_MQTT_USERNAME")
        if user:
            self.client.username_pw_set(user, os.environ.get("EDGE_MQTT_PASSWORD"))
        self.status_topic = f"edge/{DEVICE}/status"
        self.client.will_set(self.status_topic, json.dumps({"device_uuid": DEVICE, "state": "offline"}),
                             qos=1, retain=True)
        self.client.on_connect = lambda c, *_: self.status("online")
        # overrides for when the address in /edge/config is not reachable from here (e.g. inside Docker)
        self.client.connect(os.environ.get("EDGE_MQTT_HOST") or config["mqtt"]["host"],
                            int(os.environ.get("EDGE_MQTT_PORT") or config["mqtt"]["port"]))
        self.client.loop_start()

    def heartbeat(self, hb: dict) -> None:
        self.client.publish(f"edge/{DEVICE}/heartbeat", json.dumps({"device_uuid": DEVICE, **hb}), qos=0)

    def status(self, state: str) -> None:
        self.client.publish(self.status_topic, json.dumps({"device_uuid": DEVICE, "state": state, "timestamp": now()}),
                            qos=1, retain=True)

    def camera_status(self, code: str, status: dict) -> None:
        self.client.publish(f"edge/{DEVICE}/cameras/{code}/status", json.dumps({"camera_id": code, **status}), qos=0)

    def log(self, entry: dict) -> None:
        self.client.publish(f"edge/{DEVICE}/cameras/{entry['camera_id']}/logs",
                            json.dumps({"device_id": DEVICE, **entry}), qos=1)

    def close(self) -> None:
        self.client.publish(self.status_topic, json.dumps({"device_uuid": DEVICE, "state": "offline",
                                                           "timestamp": now()}), qos=1, retain=True).wait_for_publish(3)
        self.client.loop_stop()


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

    # 1. sync the complete camera list -> stream paths
    listed = [{"code": c.partition(":")[0], "name": c.partition(":")[2] or c.partition(":")[0]} for c in CAMERAS]
    result = api("PUT", "/edge/cameras", {"cameras": listed})
    cams: dict[str, dict] = {c["camera_id"]: c for c in result["cameras"]}
    for code, cam in cams.items():
        log.info("camera %s -> %s", code, cam["stream_path"])
    if result["missing"]:
        log.info("no longer listed (disabled on the platform): %s", ", ".join(result["missing"]))
    config = api("GET", "/edge/config")

    # 2. telemetry: HTTP with the device key (default), or the legacy shared MQTT account
    reload = threading.Event()
    if TELEMETRY == "mqtt":
        telemetry = MqttTelemetry(config)
    else:
        telemetry = HttpTelemetry(on_config_changed=reload.set)
        telemetry.status("online")
    log.info("telemetry over %s", TELEMETRY.upper())

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
        if reload.is_set():
            reload.clear()
            config = api("GET", "/edge/config")  # platform-side change (camera renamed, site moved, ...)
            log.info("config re-fetched: %d camera(s)", len(config["cameras"]))
        if tick % 10 == 0:
            load = os.getloadavg()[0] / (os.cpu_count() or 1) * 100
            telemetry.heartbeat({
                "timestamp": now(), "cpu_usage": min(100.0, round(load, 1)),
                "memory_usage": 0, "agent_version": "generic-edge/1.1", "hostname": socket.gethostname(),
                # the models running right now and which cameras use them (shown on the AI Models page)
                "models": [{"name": "demo-detector", "version": "1.0", "type": "yolo11",
                            "task": "person / helmet / zone intrusion", "cameras": list(cams)}],
            })
        if tick % 5 == 0:
            for code, pusher in pushers.items():
                telemetry.camera_status(code, {
                    "timestamp": now(), "rtsp_status": "online", "ai_status": "running",
                    "stream_status": "streaming" if pusher.alive else "connecting",
                    "input_fps": FPS, "inference_fps": 5, "output_fps": FPS if pusher.alive else 0,
                    "resolution": f"{WIDTH}x{HEIGHT}", "last_frame_at": now(),
                })
        if tick % 7 == 0:
            for code in cams:
                for entry in fake_recognition(code):
                    entry.update(event_id=uuid.uuid4().hex, camera_id=code, timestamp=now(),
                                 snapshot_key=upload_snapshot(code, grab_test_jpeg()))
                    telemetry.log(entry)
        if tick % 20 == 0:
            # a lifecycle event: opened now, updated (same event_id) a few seconds later
            code = random.choice(list(cams))
            event_id = f"leave-{uuid.uuid4().hex[:12]}"
            telemetry.log({
                "event_id": event_id, "camera_id": code, "timestamp": now(),
                "event_type": "office.leave", "severity": "warning", "status": "open",
                "message": "S01 left the seat", "data": {"seat_id": "S01", "leave_time": now()},
            })
            open_events.append((time.monotonic() + 8, code, event_id))
        for item in [e for e in open_events if e[0] <= time.monotonic()]:
            open_events.remove(item)
            _, code, event_id = item
            telemetry.log({
                "event_id": event_id, "camera_id": code, "event_type": "office.leave",
                "severity": "info", "status": "returned", "message": "S01 back at the seat",
                "data": {"return_time": now(), "away_seconds": 8},
            })

    for pusher in pushers.values():
        pusher.stop()
    telemetry.close()

if __name__ == "__main__":
    main()
