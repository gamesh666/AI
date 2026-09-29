"""Detector interface. Every inference backend (mock, Ultralytics YOLO, ONNX, TensorRT, …) implements it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any

from agent.core.frame_queue import Frame


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def scaled(self, sx: float, sy: float) -> BoundingBox:
        return BoundingBox(self.x1 * sx, self.y1 * sy, self.x2 * sx, self.y2 * sy)

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    def iou(self, other: BoundingBox) -> float:
        ix = max(0.0, min(self.x2, other.x2) - max(self.x1, other.x1))
        iy = max(0.0, min(self.y2, other.y2) - max(self.y1, other.y1))
        inter = ix * iy
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def with_track(self, track_id: int) -> Detection:
        return replace(self, track_id=track_id)


class Detector(ABC):
    """One detector instance belongs to one camera pipeline (no cross-thread sharing)."""

    name: str = "base"

    def __init__(self, labels: list[str] | None = None) -> None:
        self.labels = labels or []

    @abstractmethod
    def load(self) -> None:
        """Load weights / allocate device memory. Called in the inference thread before detect()."""

    @abstractmethod
    def detect(self, frame: Frame) -> list[Detection]:
        """Run inference on one frame. Coordinates are in the frame's pixel space."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources."""
