"""Simulated camera sources for the edge agent.

    file:///media/site.mp4[?loop=1]   local video file, played at its native frame rate, looped
    mock://scene?seed=N&width=W&height=H&fps=F   generated frames (no ffmpeg / RTSP needed; unit tests)

For RTSP-level simulation (the edge connecting to "IP cameras") use the fake-camera containers instead;
they publish real RTSP streams, so the production RTSP source is exercised unchanged.
"""

from __future__ import annotations

import math
import time
from urllib.parse import parse_qs, unquote, urlsplit

import cv2
import numpy as np
from agent.camera.capture import FrameSource


class _Pacer:
    def __init__(self, fps: float) -> None:
        self._interval = 1.0 / max(fps, 1.0)
        self._next = time.monotonic()

    def wait(self) -> None:
        delay = self._next - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self._next = max(self._next + self._interval, time.monotonic() - self._interval)


class FileSource(FrameSource):
    def __init__(self, url: str) -> None:
        parts = urlsplit(url)
        self._path = unquote(parts.path)
        self._loop = parse_qs(parts.query).get("loop", ["1"])[0] != "0"
        self._cap: cv2.VideoCapture | None = None
        self._pacer: _Pacer | None = None

    def open(self) -> None:
        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            raise FileNotFoundError(f"cannot open video file {self._path}")
        self._cap = cap
        self._pacer = _Pacer(cap.get(cv2.CAP_PROP_FPS) or 25.0)

    def read(self) -> np.ndarray | None:
        if self._cap is None or self._pacer is None:
            return None
        self._pacer.wait()
        ok, frame = self._cap.read()
        if not ok and self._loop:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class SyntheticSource(FrameSource):
    """Moving shapes on a street-like background; cheap enough for many cameras and CI."""

    def __init__(self, url: str) -> None:
        params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self._seed = int(params.get("seed", 1))
        self._w = int(params.get("width", 1280))
        self._h = int(params.get("height", 720))
        self._fps = float(params.get("fps", 25))
        self._pacer: _Pacer | None = None
        self._t0 = time.monotonic()

    def open(self) -> None:
        self._pacer = _Pacer(self._fps)

    def read(self) -> np.ndarray | None:
        if self._pacer is None:
            return None
        self._pacer.wait()
        t = time.monotonic() - self._t0
        w, h = self._w, self._h
        frame = np.empty((h, w, 3), dtype=np.uint8)
        frame[:] = (45, 48, 52)
        frame[: h // 3] = (70 + 10 * (self._seed % 3), 60, 50)
        for i in range(3):
            y = h // 3 + (i + 1) * h // 6
            cv2.line(frame, (0, y), (w, y), (95, 95, 95), 2)
        for i in range(3):
            phase = t / (6 + 2 * i) + self._seed + i
            x = int((math.sin(phase) + 1) / 2 * (w - w // 8))
            y = h // 3 + i * h // 6 + 10
            cv2.rectangle(frame, (x, y), (x + w // 8, y + h // 10), (60 + 60 * i, 140, 200 - 50 * i), -1)
        cv2.putText(frame, f"SIMULATED CAMERA {self._seed}", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (210, 210, 210), 1, cv2.LINE_AA)
        return frame

    def close(self) -> None:
        self._pacer = None
