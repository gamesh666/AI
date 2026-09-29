"""Detector interface. Every inference backend (mock, YOLO/PyTorch, ONNX, TensorRT…) implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox


class Detector(ABC):
    """Thread-safety: one detector instance is used by one camera pipeline thread."""

    name: str = "base"

    def __init__(self, labels: list[str] | None = None) -> None:
        self.labels = labels or []

    @abstractmethod
    def load(self) -> None:
        """Load weights / allocate device memory. Called once before the first detect()."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run inference on a BGR frame (H x W x 3, uint8)."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources."""
