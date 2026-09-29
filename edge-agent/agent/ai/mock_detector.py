"""Mock detector: returns the objects of the synthetic scene (plus a little noise).

On `mock://` cameras the boxes line up with the rendered objects; on real cameras it produces
plausible moving boxes, so the full pipeline can be exercised without a GPU or model weights.
"""

from __future__ import annotations

import random

from agent.ai.detector import BoundingBox, Detection, Detector
from agent.camera.synthetic import SyntheticScene
from agent.core.frame_queue import Frame


class MockDetector(Detector):
    name = "mock"

    def __init__(self, seed: int = 1, labels: list[str] | None = None) -> None:
        super().__init__(labels)
        self._scene = SyntheticScene(seed=seed)
        self._rng = random.Random(seed)

    def load(self) -> None:
        pass

    def detect(self, frame: Frame) -> list[Detection]:
        out = []
        for obj in self._scene.objects_at(frame.captured_at, frame.width, frame.height):
            jitter = [self._rng.uniform(-3, 3) for _ in range(4)]
            x1, y1, x2, y2 = (v + j for v, j in zip(obj.box, jitter, strict=True))
            out.append(
                Detection(
                    class_id=obj.class_id,
                    class_name=obj.class_name,
                    confidence=round(self._rng.uniform(0.62, 0.98), 3),
                    bbox=BoundingBox(max(0, x1), max(0, y1), min(frame.width, x2), min(frame.height, y2)),
                )
            )
        return out
