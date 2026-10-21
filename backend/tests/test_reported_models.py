import pytest
from pydantic import ValidationError

from aivms_shared.payloads import Heartbeat
from app.services.mappers import model_for_camera


def _hb(**kw):
    return Heartbeat.model_validate({"device_uuid": "REACH01", "cpu_usage": 1, "memory_usage": 1,
                                     "agent_version": "x", **kw})


def test_models_are_optional_and_none_means_not_reported():
    assert _hb().models is None
    assert _hb(models=[]).models == []


def test_reported_model_fields():
    hb = _hb(models=[{"name": "yolo11n", "version": "2026.09", "type": "yolo11", "task": "person / cell phone",
                      "labels": ["person", "cell phone"], "cameras": ["bimer-back-left"], "extra": "ignored"}])
    m = hb.models[0]
    assert (m.name, m.version, m.cameras) == ("yolo11n", "2026.09", ["bimer-back-left"])
    with pytest.raises(ValidationError):
        _hb(models=[{"version": "1"}])  # name is required


def test_model_for_camera():
    reported = [{"name": "yolo11n", "version": "1", "cameras": ["cam01", "cam02"]},
                {"name": "ppe", "cameras": ["cam02"]}]
    assert model_for_camera(reported, "cam01") == "yolo11n 1"
    assert model_for_camera(reported, "cam02") == "yolo11n 1, ppe"
    assert model_for_camera(reported, "cam03") is None
    # a single model without a camera list applies to every camera of the edge
    assert model_for_camera([{"name": "yolo11n"}], "camX") == "yolo11n"
    assert model_for_camera(None, "cam01") is None
