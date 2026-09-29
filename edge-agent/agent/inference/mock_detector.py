"""Mock detector: emits plausible random detections so the whole pipeline can run without a GPU/model."""

from __future__ import annotations

import random

import numpy as np

from agent.inference.base import BoundingBox, Detection, Detector

DEFAULT_LABELS = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]


class MockDetector(Detector):
    name = "mock"

    def __init__(self, labels: list[str] | None = None, probability: float = 0.15, seed: int | None = None) -> None:
        super().__init__(labels or DEFAULT_LABELS)
        self.probability = probability
        self._rng = random.Random(seed)

    def load(self) -> None:
        pass

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._rng.random() > self.probability:
            return []
        h, w = frame.shape[:2]
        detections = []
        for _ in range(self._rng.randint(1, 3)):
            class_id = self._rng.randrange(min(len(self.labels), 6))
            bw = self._rng.uniform(0.1, 0.35) * w
            bh = self._rng.uniform(0.2, 0.6) * h
            x1 = self._rng.uniform(0, w - bw)
            y1 = self._rng.uniform(0, h - bh)
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=self.labels[class_id],
                    confidence=round(self._rng.uniform(0.4, 0.99), 3),
                    bbox=BoundingBox(round(x1), round(y1), round(x1 + bw), round(y1 + bh)),
                )
            )
        return detections
