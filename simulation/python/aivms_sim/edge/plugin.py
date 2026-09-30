"""Edge-agent plugin: EDGE_PLUGINS=aivms_sim.edge.plugin

Registers simulation implementations into the agent's registries. The agent itself stays unaware of
them — switching to real hardware is purely configuration:

    camera source   mock:// / file://  ->  rtsp://<camera-ip>/...      (Camera settings in the platform)
    detector        DETECTOR_TYPE=mock ->  DETECTOR_TYPE=yolo
    metrics         EDGE_METRICS_PROVIDER=simulated -> system
"""

from __future__ import annotations

import zlib

from agent.ai.factory import DetectorOptions, register_detector
from agent.camera.capture import register_source
from agent.config.models import CameraConfig
from agent.telemetry.system_metrics import register_metrics_provider

from aivms_sim.edge.metrics import SimulatedMetrics
from aivms_sim.edge.mock_detector import MockDetector
from aivms_sim.edge.sources import FileSource, SyntheticSource


def _mock_detector(camera: CameraConfig, opts: DetectorOptions) -> MockDetector:
    labels = camera.ai_model.labels if camera.ai_model else None
    # deterministic per camera, different between cameras
    return MockDetector(labels=labels, seed=zlib.crc32(camera.camera_id.encode()))


def register() -> None:
    register_source("mock", SyntheticSource)
    register_source("file", FileSource)
    register_detector("mock", _mock_detector)
    register_metrics_provider("simulated", SimulatedMetrics)
