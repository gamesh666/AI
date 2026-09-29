"""Ultralytics YOLO detector (YOLOv8 / YOLO11 / …). Inference always runs on the edge device.

Requires `pip install -r requirements-yolo.txt`. `model_path` may be a .pt, an exported .onnx or a
TensorRT .engine — Ultralytics picks the runtime from the file type.
"""

from __future__ import annotations

import logging

from agent.ai.detector import BoundingBox, Detection, Detector
from agent.core.frame_queue import Frame

logger = logging.getLogger(__name__)


class YoloDetector(Detector):
    name = "yolo"

    def __init__(self, model_path: str, labels: list[str] | None = None, device: str = "cuda:0",
                 conf: float = 0.25, imgsz: int = 640) -> None:
        super().__init__(labels)
        self.model_path = model_path
        self.device = device
        self.conf = conf
        self.imgsz = imgsz
        self._model = None

    def load(self) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is not installed; pip install -r requirements-yolo.txt") from exc
        device = self.device
        if device.startswith("cuda"):
            try:
                import torch

                if not torch.cuda.is_available():
                    logger.warning("CUDA not available; YOLO falls back to CPU")
                    device = "cpu"
            except ImportError:
                device = "cpu"
        self._model = YOLO(self.model_path)
        self._device = device
        # warm-up so the first real frame does not pay for lazy initialisation
        import numpy as np

        self._model.predict(np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8), device=device, verbose=False)
        logger.info("YOLO model %s loaded on %s", self.model_path, device)

    def detect(self, frame: Frame) -> list[Detection]:
        if self._model is None:
            raise RuntimeError("detector not loaded")
        result = self._model.predict(frame.image, conf=self.conf, imgsz=self.imgsz, device=self._device,
                                     verbose=False)[0]
        names = result.names
        boxes = result.boxes
        detections = []
        for xyxy, conf, cls in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), strict=True):
            class_id = int(cls)
            label = self.labels[class_id] if class_id < len(self.labels) else names.get(class_id, str(class_id))
            detections.append(Detection(class_id, label, round(float(conf), 4), BoundingBox(*map(float, xyxy))))
        return detections

    def close(self) -> None:
        self._model = None
