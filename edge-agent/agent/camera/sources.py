"""Frame sources used for inference.

RTSPFrameSource   rtsp:// / rtsps://   OpenCV + FFmpeg backend, background reader keeps only the latest frame
SyntheticSource   mock://              generated frames, lets the platform run end-to-end without cameras
"""

from __future__ import annotations

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# force TCP for RTSP inside OpenCV's FFmpeg backend (more reliable over WAN)
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")


class SourceState(StrEnum):
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class FrameSource(ABC):
    def __init__(self) -> None:
        self.state = SourceState.CONNECTING
        self.error: str | None = None
        self.fps: float = 0.0

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def latest(self) -> np.ndarray | None:
        """Most recent frame (BGR) or None if nothing is available yet."""


class RTSPFrameSource(FrameSource):
    def __init__(self, url: str, reconnect_max_delay: float = 30.0) -> None:
        super().__init__()
        self._url = url
        self._max_delay = reconnect_max_delay
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rtsp-reader", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def latest(self) -> np.ndarray | None:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def _run(self) -> None:
        delay = 1.0
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.state, self.error = SourceState.OFFLINE, "cannot open stream"
                cap.release()
                self._stop.wait(delay)
                delay = min(delay * 2, self._max_delay)
                continue
            self.state, self.error, delay = SourceState.ONLINE, None, 1.0
            frames, window_start = 0, time.monotonic()
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    self.state, self.error = SourceState.OFFLINE, "stream read failed"
                    break
                with self._lock:
                    self._frame = frame
                frames += 1
                elapsed = time.monotonic() - window_start
                if elapsed >= 5:
                    self.fps, frames, window_start = round(frames / elapsed, 1), 0, time.monotonic()
            cap.release()
        self.state = SourceState.OFFLINE


class SyntheticSource(FrameSource):
    """Moving box + clock on a gradient. `mock://testsrc?pattern=N` varies the colours."""

    def __init__(self, width: int = 1280, height: int = 720, pattern: int = 1) -> None:
        super().__init__()
        self._w, self._h, self._pattern = width, height, pattern
        self._t0 = time.monotonic()

    def start(self) -> None:
        self.state, self.fps = SourceState.ONLINE, 15.0

    def stop(self) -> None:
        self.state = SourceState.OFFLINE

    def latest(self) -> np.ndarray | None:
        t = time.monotonic() - self._t0
        frame = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        frame[:, :, (self._pattern - 1) % 3] = np.linspace(40, 160, self._w, dtype=np.uint8)
        x = int((np.sin(t / 3) + 1) / 2 * (self._w - 200))
        cv2.rectangle(frame, (x, self._h // 3), (x + 200, self._h // 3 + 300), (255, 255, 255), -1)
        cv2.putText(frame, datetime.now(UTC).strftime("%H:%M:%S"), (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        return frame


def create_source(url: str) -> FrameSource:
    if url.startswith("mock://"):
        pattern = 1
        if "pattern=" in url:
            try:
                pattern = int(url.split("pattern=")[1].split("&")[0])
            except ValueError:
                pass
        return SyntheticSource(pattern=pattern)
    return RTSPFrameSource(url)
