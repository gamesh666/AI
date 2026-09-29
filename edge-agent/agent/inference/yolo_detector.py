"""YOLO detector — interface placeholder.

The MVP ships with MockDetector only. To implement real inference:

    pip install -r requirements-yolo.txt

    def load(self):
        from ultralytics import YOLO
        self._model = YOLO(self.model_path)
        self._model.to(self.device)                 # "cuda:0" / "cpu"

    def detect(self, frame):
        result = self._model.predict(frame, conf=self.conf, verbose=False)[0]
        return [
            Detection(int(c), result.names[int(c)], float(p), BoundingBox(*map(float, xyxy)))
            for xyxy, p, c in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(),
                                  result.boxes.cls.tolist())
        ]

Inference always runs on the edge device; only the resulting detections are sent to the server.
"""

from __future__ import annotations

import numpy as np

from agent.inference.base import Detection, Detector


class YoloDetector(Detector):
    name = "yolo"

    def __init__(self, model_path: str, labels: list[str] | None = None, device: str = "cuda:0",
                 conf: float = 0.25) -> None:
        super().__init__(labels)
        self.model_path = model_path
        self.device = device
        self.conf = conf
        self._model = None

    def load(self) -> None:
        raise NotImplementedError(
            "YOLO inference is not implemented in the MVP. Use EDGE_DETECTOR=mock, "
            "or implement YoloDetector.load/detect (see module docstring)."
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError
