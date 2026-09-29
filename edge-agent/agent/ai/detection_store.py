"""Latest detection result of one camera, shared between the inference and render workers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from agent.ai.detector import Detection


@dataclass(frozen=True, slots=True)
class DetectionResult:
    detections: list[Detection]
    frame_width: int
    frame_height: int
    monotonic: float


class DetectionStore:
    def __init__(self) -> None:
        self._result: DetectionResult | None = None
        self._lock = threading.Lock()

    def set(self, result: DetectionResult) -> None:
        with self._lock:
            self._result = result

    def latest(self, max_age_seconds: float, now: float | None = None) -> DetectionResult | None:
        """Option A: reuse the last result while it is fresh enough; stale boxes are not drawn."""
        with self._lock:
            result = self._result
        if result is None:
            return None
        if (now if now is not None else time.monotonic()) - result.monotonic > max_age_seconds:
            return None
        return result
