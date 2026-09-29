from __future__ import annotations

from agent.api_client.models import ModelConfig
from agent.inference.base import Detector
from agent.inference.mock_detector import MockDetector
from agent.inference.yolo_detector import YoloDetector


def create_detector(kind: str, model: ModelConfig | None, mock_probability: float = 0.15) -> Detector:
    labels = model.labels if model else None
    if kind == "mock":
        return MockDetector(labels=labels, probability=mock_probability)
    if kind == "yolo":
        if model is None:
            raise ValueError("YOLO detector requires an AI model assigned to the camera")
        return YoloDetector(model_path=model.model_path, labels=labels)
    raise ValueError(f"unknown detector '{kind}'")
