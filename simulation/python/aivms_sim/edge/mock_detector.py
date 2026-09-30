"""MockDetector: a drop-in replacement for the YOLO detector when there is no model or GPU.

Every few seconds a new object (person / car / truck / excavator) appears, moves across the frame
for a while and leaves. Output is exactly what YoloDetector returns — `agent.ai.detector.Detection`
with class_id / class_name / confidence / bbox — so tracking, overlay, events, MQTT, database and
frontend cannot tell the difference.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from agent.ai.detector import BoundingBox, Detection, Detector
from agent.core.frame_queue import Frame

# COCO class ids (what a stock YOLO model reports); "excavator" is not in COCO -> custom id 80
DEFAULT_CLASSES: dict[str, int] = {"person": 0, "car": 2, "truck": 7, "excavator": 80}

# relative (width, height) of each class, as a fraction of the frame height
_SHAPES: dict[str, tuple[float, float]] = {
    "person": (0.12, 0.32),
    "car": (0.34, 0.18),
    "truck": (0.48, 0.28),
    "excavator": (0.45, 0.35),
}


@dataclass
class _MockObject:
    class_name: str
    born: float
    lifetime: float
    x: float  # top-left, normalised 0..1
    y: float
    vx: float  # normalised units / second
    vy: float
    w: float  # size relative to frame height
    h: float
    base_conf: float


class MockDetector(Detector):
    name = "mock"

    def __init__(self, labels: list[str] | None = None, seed: int | None = None,
                 spawn_interval: tuple[float, float] = (1.5, 4.0), lifetime: tuple[float, float] = (5.0, 12.0),
                 max_objects: int = 4, classes: dict[str, int] | None = None, clock=time.monotonic) -> None:
        super().__init__(labels)
        self._rng = random.Random(seed)
        self._spawn_interval = spawn_interval
        self._lifetime = lifetime
        self._max = max_objects
        self._classes = classes or DEFAULT_CLASSES
        self._clock = clock
        self._objects: list[_MockObject] = []
        self._next_spawn = 0.0

    def load(self) -> None:
        self._next_spawn = self._clock()

    def class_id(self, class_name: str) -> int:
        """Same id space as the real model: its label list when available, else COCO ids."""
        if class_name in self.labels:
            return self.labels.index(class_name)
        return self._classes.get(class_name, 0)

    def _spawn(self, now: float, aspect: float) -> None:
        name = self._rng.choice(list(self._classes))
        rel_w, rel_h = _SHAPES.get(name, (0.2, 0.2))
        w = rel_w * self._rng.uniform(0.8, 1.2) / aspect  # to width-normalised units
        h = rel_h * self._rng.uniform(0.8, 1.2)
        from_left = self._rng.random() < 0.5
        speed = self._rng.uniform(0.05, 0.14) * (1 if from_left else -1)
        self._objects.append(
            _MockObject(
                class_name=name,
                born=now,
                lifetime=self._rng.uniform(*self._lifetime),
                x=-w * 0.5 if from_left else 1 - w * 0.5,
                y=self._rng.uniform(0.25, 0.95 - h),
                vx=speed,
                vy=self._rng.uniform(-0.01, 0.01),
                w=w,
                h=h,
                base_conf=self._rng.uniform(0.7, 0.95),
            )
        )

    def detect(self, frame: Frame) -> list[Detection]:
        now = self._clock()
        width, height = frame.width, frame.height
        aspect = width / height
        if now >= self._next_spawn:
            if len(self._objects) < self._max:
                self._spawn(now, aspect)
            self._next_spawn = now + self._rng.uniform(*self._spawn_interval)

        detections, alive = [], []
        for o in self._objects:
            age = now - o.born
            x, y = o.x + o.vx * age, o.y + o.vy * age
            if age > o.lifetime or x > 1.0 or x + o.w < 0.0:
                continue  # left the scene
            alive.append(o)
            x1, y1 = max(0.0, x) * width, max(0.0, y) * height
            x2, y2 = min(1.0, x + o.w) * width, min(1.0, y + o.h) * height
            if x2 - x1 < 4 or y2 - y1 < 4:
                continue
            conf = min(0.99, max(0.3, o.base_conf + self._rng.uniform(-0.05, 0.05)))
            detections.append(
                Detection(
                    class_id=self.class_id(o.class_name),
                    class_name=o.class_name,
                    confidence=round(conf, 3),
                    bbox=BoundingBox(round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)),
                )
            )
        self._objects = alive
        return detections
