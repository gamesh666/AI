from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from agent.ai.detector import Detector
from agent.ai.mock_detector import MockDetector
from agent.ai.yolo_detector import YoloDetector
from agent.config.models import CameraConfig


def create_detector(kind: str, camera: CameraConfig, device: str = "cuda:0", conf: float = 0.25) -> Detector:
    model = camera.ai_model
    labels = model.labels if model else None
    if kind == "mock":
        seed = 1
        if camera.rtsp_url.startswith("mock://"):
            seed = int(parse_qs(urlsplit(camera.rtsp_url).query).get("seed", ["1"])[0])
        return MockDetector(seed=seed, labels=labels)
    if kind == "yolo":
        if model is None:
            raise ValueError("YOLO detector requires an AI model assigned to the camera")
        return YoloDetector(model_path=model.model_path, labels=labels, device=device, conf=conf)
    raise ValueError(f"unknown detector '{kind}'")
