"""Production extension points: sources, detectors, metrics and plugins — without any simulation code."""

import sys
import types

import numpy as np
import pytest

from agent.ai import factory
from agent.ai.detector import BoundingBox, Detection, Detector
from agent.ai.factory import FallbackDetector, create_detector, register_detector
from agent.camera import capture
from agent.camera.capture import RTSPSource, create_source, register_source
from agent.core.frame_queue import Frame
from agent.plugins import load_plugins
from agent.telemetry.system_metrics import SystemMetrics, create_metrics, register_metrics_provider


class _Broken(Detector):
    name = "broken"

    def load(self):
        raise RuntimeError("model file not found")

    def detect(self, frame):
        raise AssertionError("never called")


class _Fixed(Detector):
    name = "fixed"

    def load(self):
        pass

    def detect(self, frame):
        return [Detection(0, "person", 0.9, BoundingBox(1, 2, 3, 4))]


@pytest.fixture(autouse=True)
def _isolated_registries(monkeypatch):
    monkeypatch.setattr(factory, "_DETECTORS", dict(factory._DETECTORS))
    monkeypatch.setattr(capture, "_SOURCES", dict(capture._SOURCES))


def test_production_ships_only_rtsp_and_yolo():
    assert capture.supported_schemes() == ["rtsp", "rtsps"]
    assert factory.available_detectors() == ["yolo"]
    assert isinstance(create_source("rtsp://10.0.0.1/s"), RTSPSource)
    with pytest.raises(ValueError, match="unsupported camera source 'mock://'"):
        create_source("mock://scene")


def test_unknown_detector_points_to_plugins(camera_config):
    with pytest.raises(ValueError, match="EDGE_PLUGINS"):
        create_detector("mock", camera_config())


def test_yolo_needs_a_model(camera_config):
    with pytest.raises(ValueError, match="requires an AI model"):
        create_detector("yolo", camera_config())


def test_fallback_detector_is_transparent(camera_config):
    register_detector("broken", lambda cam, opts: _Broken())
    register_detector("fixed", lambda cam, opts: _Fixed())
    det = create_detector("broken", camera_config(), fallback="fixed")
    assert isinstance(det, FallbackDetector)
    det.load()
    frame = Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), seq=1)
    assert det.name == "fixed" and det.detect(frame)[0].class_name == "person"


def test_fallback_used_when_primary_cannot_be_built(camera_config):
    register_detector("fixed", lambda cam, opts: _Fixed())
    det = create_detector("yolo", camera_config(), fallback="fixed")  # no model assigned
    assert isinstance(det, _Fixed)


def test_plugin_loader_registers_implementations(monkeypatch):
    mod = types.ModuleType("fake_plugin")
    mod.register = lambda: register_source("fake", lambda url: "fake-source")
    monkeypatch.setitem(sys.modules, "fake_plugin", mod)
    load_plugins(["fake_plugin"])
    assert create_source("fake://x") == "fake-source"

    bad = types.ModuleType("bad_plugin")
    monkeypatch.setitem(sys.modules, "bad_plugin", bad)
    with pytest.raises(RuntimeError, match="no register"):
        load_plugins(["bad_plugin"])


def test_metrics_providers():
    assert isinstance(create_metrics("system"), SystemMetrics)
    register_metrics_provider("custom", SystemMetrics)
    assert isinstance(create_metrics("custom"), SystemMetrics)
    with pytest.raises(ValueError):
        create_metrics("nope")


def test_detector_type_env_alias(monkeypatch):
    from agent.config.settings import AgentSettings

    monkeypatch.setenv("DETECTOR_TYPE", "mock")
    assert AgentSettings(device_uuid="EDGE001").detector == "mock"
    monkeypatch.delenv("DETECTOR_TYPE")
    assert AgentSettings(device_uuid="EDGE001").detector == "yolo"  # production default
