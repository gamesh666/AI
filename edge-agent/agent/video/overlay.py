"""Draws detections onto frames: bounding box + "Person 95% #123" label (+ optional HUD)."""

from __future__ import annotations

import time
from collections.abc import Sequence

import cv2
import numpy as np

from agent.ai.detector import Detection

_PALETTE = [
    (56, 56, 255), (151, 157, 255), (31, 112, 255), (29, 178, 255), (49, 210, 207), (10, 249, 72),
    (23, 204, 146), (134, 219, 61), (52, 147, 26), (187, 212, 0), (168, 153, 44), (255, 194, 0),
    (147, 69, 52), (255, 115, 100), (236, 24, 0), (255, 56, 132), (133, 0, 82), (255, 56, 203),
]


def color_for(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


def format_label(det: Detection) -> str:
    text = f"{det.class_name.capitalize()} {det.confidence * 100:.0f}%"
    return f"{text} #{det.track_id}" if det.track_id is not None else text


class OverlayRenderer:
    def __init__(self, show_hud: bool = True) -> None:
        self.show_hud = show_hud

    def draw(self, image: np.ndarray, detections: Sequence[Detection], scale_x: float = 1.0,
             scale_y: float = 1.0, hud_text: str | None = None) -> np.ndarray:
        """Draw IN PLACE on `image` (callers pass a frame they own) and return it.

        scale_x/scale_y map detection coordinates (inference frame) onto `image` when resized.
        """
        h, w = image.shape[:2]
        thickness = max(2, round(min(w, h) / 360))
        font_scale = max(0.5, min(w, h) / 1100)
        for det in detections:
            box = det.bbox.scaled(scale_x, scale_y) if (scale_x, scale_y) != (1.0, 1.0) else det.bbox
            x1, y1, x2, y2 = (int(round(v)) for v in (box.x1, box.y1, box.x2, box.y2))
            color = color_for(det.class_id)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
            label = format_label(det)
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            top = y1 - th - baseline - 4 if y1 - th - baseline - 4 > 0 else y1
            cv2.rectangle(image, (x1, top), (x1 + tw + 6, top + th + baseline + 4), color, -1)
            cv2.putText(image, label, (x1 + 3, top + th + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        (255, 255, 255), 1, cv2.LINE_AA)
        if self.show_hud and hud_text:
            stamp = f"{hud_text}  {time.strftime('%Y-%m-%d %H:%M:%S')}"
            (tw, th), baseline = cv2.getTextSize(stamp, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            cv2.rectangle(image, (6, 6), (14 + tw, 14 + th + baseline), (0, 0, 0), -1)
            cv2.putText(image, stamp, (10, 10 + th), cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return image
