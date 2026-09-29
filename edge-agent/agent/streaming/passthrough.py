"""Optional passthrough of the ORIGINAL camera stream to original/<site>/<device>/<camera>.

No decoding/re-encoding (`-c copy`). Opens a second RTSP session to the camera, so it is off by
default (cameras.original_stream_enabled).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections import deque

from agent.core.backoff import Backoff
from agent.core.worker import Worker
from agent.streaming.factory import PublishEndpoint
from agent.streaming.rtsp_publisher import build_rtsp_url
from agent.streaming.srt_publisher import build_srt_url

logger = logging.getLogger(__name__)


def build_passthrough_command(ffmpeg: str, source_url: str, endpoint: PublishEndpoint, path: str) -> list[str]:
    head = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-rtsp_transport", "tcp", "-timeout", "5000000", "-i", source_url,
            "-map", "0:v:0", "-map", "0:a?", "-c", "copy"]
    if endpoint.protocol == "srt":
        return [*head, "-f", "mpegts", build_srt_url(endpoint.base_url, path, endpoint.username, endpoint.password)]
    return [*head, "-f", "rtsp", "-rtsp_transport", "tcp",
            build_rtsp_url(endpoint.base_url, path, endpoint.username, endpoint.password)]


class PassthroughWorker(Worker):
    def __init__(self, camera_id: str, source_url: str, endpoint: PublishEndpoint, path: str,
                 ffmpeg: str = "ffmpeg") -> None:
        super().__init__(f"original-{camera_id}")
        self._cmd = build_passthrough_command(ffmpeg, source_url, endpoint, path)
        self._ffmpeg = ffmpeg
        self._proc: subprocess.Popen | None = None
        self._backoff = Backoff()
        self._stderr: deque[str] = deque(maxlen=10)

    def step(self) -> None:
        if not shutil.which(self._ffmpeg):
            raise RuntimeError("ffmpeg not found")
        self._proc = subprocess.Popen(self._cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE, text=True)
        assert self._proc.stderr is not None
        for line in self._proc.stderr:
            self._stderr.append(line.rstrip())
        code = self._proc.wait()
        if self.stopped:
            return
        delay = self._backoff.next_delay()
        logger.warning("[%s] passthrough exited (%s): %s; restart in %.0fs", self.name, code,
                       " | ".join(list(self._stderr)[-2:]), delay)
        self.sleep(delay)

    def on_stop(self) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
