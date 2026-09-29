"""Render worker: produces the annotated video at a constant `stream_fps`.

Every tick it takes the newest captured frame (repeating the previous one if the camera is slower),
resizes it to the output resolution and draws the latest detections (Option A: the last inference
result is reused until it is older than `detection_hold_seconds`). Encoders need a constant frame
rate, which is why the render clock — not the camera — drives the output.
"""

from __future__ import annotations

import time

import cv2

from agent.ai.detection_store import DetectionStore
from agent.ai.tracking import Tracker
from agent.core.frame_queue import BoundedFrameQueue, Frame
from agent.core.worker import Worker
from agent.video.overlay import OverlayRenderer


class RenderWorker(Worker):
    def __init__(self, camera_id: str, source: BoundedFrameQueue, output: BoundedFrameQueue,
                 overlay: OverlayRenderer, store: DetectionStore | None, tracker: Tracker | None,
                 stream_fps: int, width: int | None, height: int | None, hold_seconds: float,
                 hud_text: str | None = None) -> None:
        super().__init__(f"render-{camera_id}")
        self._source = source
        self._output = output
        self._overlay = overlay
        self._store = store  # None when AI is disabled: plain video
        self._tracker = tracker
        self._interval = 1.0 / max(stream_fps, 1)
        self._size = (width, height) if width and height else None
        self._hold = hold_seconds
        self._hud = hud_text
        self._last: Frame | None = None
        self._next_tick = time.monotonic()
        self._seq = 0

    def step(self) -> None:
        frame = self._source.get_latest(timeout=0 if self._last is not None else 1.0)
        if frame is not None:
            self._last = frame
        if self._last is None:
            return  # no frame yet (camera connecting)

        src = self._last
        image = src.image
        sx = sy = 1.0
        if self._size and (src.width, src.height) != self._size:
            image = cv2.resize(image, self._size, interpolation=cv2.INTER_AREA)
            sx, sy = self._size[0] / src.width, self._size[1] / src.height
        else:
            image = image.copy()  # never draw on a frame other workers may still read

        if self._store is not None:
            detections = self._tracker.predict(time.monotonic()) if self._tracker else None  # Option B hook
            if detections is None:
                result = self._store.latest(self._hold)
                detections = result.detections if result else []
                if result and (result.frame_width, result.frame_height) != (src.width, src.height):
                    sx *= src.width / result.frame_width
                    sy *= src.height / result.frame_height
            self._overlay.draw(image, detections, sx, sy, self._hud)
        elif self._hud:
            self._overlay.draw(image, [], hud_text=self._hud)

        self._seq += 1
        self._output.put(Frame(image=image, seq=self._seq, captured_at=src.captured_at))

        # constant output rate
        self._next_tick += self._interval
        now = time.monotonic()
        if self._next_tick < now - self._interval:  # fell behind (slow CPU): resync instead of bursting
            self._next_tick = now
        self.sleep(self._next_tick - now)
