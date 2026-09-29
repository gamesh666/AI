"""FFmpeg relay: camera RTSP -> MediaMTX (RTSP publish), no re-encoding.

The browser never talks to the camera; MediaMTX serves WebRTC/HLS to viewers.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from collections import deque
from urllib.parse import quote, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


def build_publish_url(base_url: str, stream_id: str, username: str, password: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{parts.netloc}"
    path = f"{parts.path}/{stream_id}"
    return urlunsplit(parts._replace(netloc=netloc, path=path))


def build_ffmpeg_command(ffmpeg: str, source_url: str, publish_url: str) -> list[str]:
    common_out = ["-f", "rtsp", "-rtsp_transport", "tcp", publish_url]
    if source_url.startswith("mock://"):
        pattern = "testsrc2" if "pattern=2" not in source_url else "smptebars"
        # synthetic test pattern, H.264 baseline-friendly settings (no B-frames) for WebRTC
        return [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-re",
            "-f", "lavfi", "-i", f"{pattern}=size=1280x720:rate=15",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-pix_fmt", "yuv420p", "-g", "30", "-bf", "0",
            *common_out,
        ]
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", "tcp", "-timeout", "5000000",
        "-i", source_url,
        "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
        *common_out,
    ]


class FFmpegRelay:
    def __init__(self, ffmpeg: str, source_url: str, publish_url: str, name: str) -> None:
        self._cmd = build_ffmpeg_command(ffmpeg, source_url, publish_url)
        self._name = name
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._supervise, name=f"relay-{name}", daemon=True)
        self._stderr: deque[str] = deque(maxlen=20)
        self.running = False

    @staticmethod
    def available(ffmpeg: str) -> bool:
        return shutil.which(ffmpeg) is not None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._thread.join(timeout=6)

    def _supervise(self) -> None:
        delay = 2.0
        while not self._stop.is_set():
            logger.info("[%s] starting ffmpeg relay", self._name)
            self._proc = subprocess.Popen(self._cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            self.running = True
            assert self._proc.stderr is not None
            for line in self._proc.stderr:
                self._stderr.append(line.rstrip())
            code = self._proc.wait()
            self.running = False
            if self._stop.is_set():
                break
            logger.warning("[%s] ffmpeg exited (%s): %s; restart in %.0fs",
                           self._name, code, " | ".join(list(self._stderr)[-3:]), delay)
            self._stop.wait(delay)
            delay = min(delay * 2, 60)
