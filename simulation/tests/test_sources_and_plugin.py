import cv2
import numpy as np
from agent.ai.factory import DetectorOptions, FallbackDetector, create_detector
from agent.camera.capture import create_source
from agent.config.models import ModelConfig
from agent.core.frame_queue import Frame
from agent.telemetry.system_metrics import create_metrics

from aivms_sim.edge.mock_detector import MockDetector
from aivms_sim.edge.sources import FileSource, SyntheticSource


def test_plugin_adds_sources_without_touching_rtsp():
    assert isinstance(create_source("mock://scene?seed=2&width=64&height=48&fps=50"), SyntheticSource)
    assert isinstance(create_source("file:///tmp/x.mp4"), FileSource)
    assert type(create_source("rtsp://10.0.0.1/s")).__name__ == "RTSPSource"


def test_synthetic_source_frames():
    src = create_source("mock://scene?seed=2&width=64&height=48&fps=100")
    src.open()
    frame = src.read()
    assert frame.shape == (48, 64, 3) and frame.dtype == np.uint8


def test_file_source_loops(tmp_path):
    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 100, (64, 48))
    for i in range(5):
        writer.write(np.full((48, 64, 3), i * 40, dtype=np.uint8))
    writer.release()
    src = create_source(f"file://{path}")
    src.open()
    frames = [src.read() for _ in range(12)]  # more frames than the file has
    src.close()
    assert all(f is not None and f.shape == (48, 64, 3) for f in frames)


def test_mock_detector_selected_by_name(camera_config):
    det = create_detector("mock", camera_config())
    assert isinstance(det, MockDetector)


def test_yolo_falls_back_to_mock_without_ultralytics(camera_config):
    cam = camera_config(ai_model=ModelConfig(id="1", name="yolov8n", version="8", model_type="yolov8",
                                             labels=["person"], model_path="/models/missing.pt"))
    det = create_detector("yolo", cam, DetectorOptions(device="cpu"), fallback="mock")
    assert isinstance(det, FallbackDetector)
    det.load()  # ultralytics / model not available here -> mock
    assert det.name == "mock"
    det.detect(Frame(image=np.zeros((720, 1280, 3), dtype=np.uint8), seq=1))


def test_simulated_gpu_metrics():
    gpu = create_metrics("simulated").gpu()
    assert gpu.name and gpu.total_memory_mb and 0 <= gpu.usage <= 100 and gpu.temperature > 0
