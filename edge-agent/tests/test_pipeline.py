import numpy as np
import pytest

from agent.camera.stream_relay import build_ffmpeg_command, build_publish_url
from agent.inference.base import BoundingBox, Detection
from agent.inference.factory import create_detector
from agent.inference.mock_detector import MockDetector
from agent.pipeline.event_builder import build_event
from agent.pipeline.throttle import EventThrottle


def test_mock_detector_returns_valid_boxes():
    det = MockDetector(probability=1.0, seed=42)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    results = det.detect(frame)
    assert 1 <= len(results) <= 3
    for d in results:
        assert 0 <= d.bbox.x1 < d.bbox.x2 <= 1280
        assert 0 <= d.bbox.y1 < d.bbox.y2 <= 720
        assert 0 <= d.confidence <= 1


def test_mock_detector_probability_zero():
    assert MockDetector(probability=0.0).detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_factory_rejects_unknown():
    with pytest.raises(ValueError):
        create_detector("nope", None)


def test_throttle_cooldown():
    now = [0.0]
    t = EventThrottle(5, clock=lambda: now[0])
    assert t.allow("person")
    assert not t.allow("person")
    assert t.allow("car")
    now[0] = 5.1
    assert t.allow("person")


def test_event_matches_contract():
    d = Detection(0, "person", 0.95, BoundingBox(100, 120, 400, 650))
    ev = build_event("edge-001", "cam-001", "yolov8n", [d], (720, 1280, 3), "snapshots/k.jpg")
    body = ev.model_dump(mode="json")
    assert body["device_id"] == "edge-001"
    assert body["camera_id"] == "cam-001"
    assert body["detections"][0] == {
        "class_id": 0,
        "class_name": "person",
        "confidence": 0.95,
        "bbox": {"x1": 100, "y1": 120, "x2": 400, "y2": 650},
    }
    assert body["frame_width"] == 1280


def test_publish_url_escapes_credentials():
    url = build_publish_url("rtsp://mediamtx:8554", "cam-1", "edge-001", "k/e:y")
    assert url == "rtsp://edge-001:k%2Fe%3Ay@mediamtx:8554/cam-1"


def test_ffmpeg_copy_for_rtsp():
    cmd = build_ffmpeg_command("ffmpeg", "rtsp://cam/1", "rtsp://x/y")
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
