"""Deterministic synthetic scene for `mock://scene?seed=N` cameras.

Lets the whole platform (capture → AI → overlay → H.264 → MediaMTX → WebRTC) run without real
cameras. The mock detector evaluates the same scene, so its boxes line up with what is drawn.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np

CLASSES = [(0, "person"), (2, "car"), (7, "truck"), (1, "bicycle")]


@dataclass(frozen=True, slots=True)
class SceneObject:
    object_id: int
    class_id: int
    class_name: str
    box: tuple[int, int, int, int]  # x1, y1, x2, y2


def parse_mock_url(url: str) -> dict[str, str]:
    """mock://scene?seed=2&width=1280&height=720&fps=25"""
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


class SyntheticScene:
    def __init__(self, seed: int = 1, objects: int = 4) -> None:
        rng = random.Random(seed)
        self.seed = seed
        self._objects = []
        for i in range(objects):
            class_id, class_name = CLASSES[rng.randrange(len(CLASSES))]
            self._objects.append(
                {
                    "id": i + 1,
                    "class_id": class_id,
                    "class_name": class_name,
                    "period": rng.uniform(25, 50),  # seconds for one lap
                    "phase": rng.uniform(0, 2 * math.pi),
                    "lane": rng.uniform(0.2, 0.8),
                    "size": rng.uniform(0.12, 0.22),
                    "visible_ratio": rng.uniform(0.6, 0.9),
                }
            )

    def objects_at(self, t: float, width: int, height: int) -> list[SceneObject]:
        out = []
        for o in self._objects:
            angle = 2 * math.pi * t / o["period"] + o["phase"]
            # object enters/leaves the scene periodically
            if (angle / (2 * math.pi)) % 1.0 > o["visible_ratio"]:
                continue
            tall = o["class_name"] in ("person", "bicycle")
            h = int(height * o["size"] * (1.6 if tall else 1.0))
            w = int(h * (0.45 if tall else 1.6))
            cx = (math.sin(angle) + 1) / 2 * (width - w) + w / 2
            cy = o["lane"] * (height - h) + h / 2 + math.sin(angle * 2) * height * 0.03
            x1, y1 = int(cx - w / 2), int(max(0, cy - h / 2))
            out.append(SceneObject(o["id"], o["class_id"], o["class_name"], (x1, y1, x1 + w, min(height, y1 + h))))
        return out

    def render(self, t: float, width: int, height: int) -> np.ndarray:
        frame = np.empty((height, width, 3), dtype=np.uint8)
        # static "street" background: gradient + lane lines
        frame[:] = (40, 45, 50)
        frame[: height // 3] = (70, 60, 50)
        for y in range(height // 3, height, max(1, height // 6)):
            cv2.line(frame, (0, y), (width, y), (90, 90, 90), 2)
        colors = {"person": (60, 180, 240), "car": (200, 120, 60), "truck": (80, 80, 200), "bicycle": (80, 200, 120)}
        for obj in self.objects_at(t, width, height):
            x1, y1, x2, y2 = obj.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), colors[obj.class_name], -1)
        cv2.putText(frame, f"SYNTHETIC CAMERA seed={self.seed}", (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        return frame
