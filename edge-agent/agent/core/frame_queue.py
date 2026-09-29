"""Bounded frame queue that drops the OLDEST frame when full.

Video pipelines must never block the producer (camera capture) on a slow consumer
(inference, encoder, network) and must never grow without bound.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class Frame:
    image: np.ndarray  # BGR, H x W x 3, uint8
    seq: int
    captured_at: float = field(default_factory=time.time)  # wall clock (for metadata)
    monotonic: float = field(default_factory=time.monotonic)

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    @property
    def height(self) -> int:
        return int(self.image.shape[0])


class BoundedFrameQueue:
    def __init__(self, maxsize: int, name: str = "") -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.name = name
        self.maxsize = maxsize
        self._items: deque[Frame] = deque()
        self._cond = threading.Condition()
        self.dropped = 0

    def put(self, frame: Frame) -> None:
        with self._cond:
            if len(self._items) >= self.maxsize:
                self._items.popleft()
                self.dropped += 1
            self._items.append(frame)
            self._cond.notify()

    def get(self, timeout: float | None = None) -> Frame | None:
        """Oldest queued frame, or None on timeout."""
        with self._cond:
            if not self._items and not self._cond.wait_for(lambda: bool(self._items), timeout):
                return None
            return self._items.popleft()

    def get_latest(self, timeout: float | None = None) -> Frame | None:
        """Newest frame; everything older is discarded (counted as dropped)."""
        with self._cond:
            if not self._items and not self._cond.wait_for(lambda: bool(self._items), timeout):
                return None
            frame = self._items.pop()
            self.dropped += len(self._items)
            self._items.clear()
            return frame

    def clear(self) -> None:
        with self._cond:
            self._items.clear()

    def __len__(self) -> int:
        with self._cond:
            return len(self._items)
