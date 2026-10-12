from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aivms_shared.payloads import EdgeLog
from app.api.v1.edge_telemetry import _own, _validate
from app.core.config import get_settings
from app.core.exceptions import PermissionDeniedError
from app.services import telemetry
from app.services.edge_log_service import EdgeLogService
from app.services.provisioning import UnprocessableError

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def device(http_ago=None, mqtt_ago=None):
    return SimpleNamespace(
        last_http_at=NOW - timedelta(seconds=http_ago) if http_ago is not None else None,
        last_mqtt_at=NOW - timedelta(seconds=mqtt_ago) if mqtt_ago is not None else None,
    )


@pytest.mark.parametrize(
    ("http_ago", "mqtt_ago", "expected"),
    [
        (None, None, None),
        (10, None, "http"),
        (None, 10, "mqtt"),
        (10, 20, "both"),
        (10, 3600, "http"),  # switched over an hour ago: MQTT no longer counts
        (3600, 3600, None),
    ],
)
def test_transport_reflects_recent_heartbeats(http_ago, mqtt_ago, expected):
    assert telemetry.transport_of(device(http_ago, mqtt_ago), now=NOW) == expected


@pytest.fixture
def mqtt_edge(monkeypatch):
    def set_enabled(value: bool):
        monkeypatch.setenv("MQTT_EDGE_ENABLED", str(value).lower())
        get_settings.cache_clear()

    yield set_enabled
    get_settings.cache_clear()


def test_commands_follow_the_transport(mqtt_edge, monkeypatch):
    monkeypatch.setattr(telemetry, "transport_of", lambda d: d)
    mqtt_edge(True)
    assert telemetry.deliver_over_http("http") is True
    assert telemetry.deliver_over_http("both") is False
    assert telemetry.deliver_over_http(None) is False
    mqtt_edge(False)
    assert telemetry.deliver_over_http("mqtt") is True  # no MQTT account any more: heartbeat queue only


def test_identity_is_filled_from_the_device_key():
    assert _own({}, "device_uuid", "REACH01") == {"device_uuid": "REACH01"}
    assert _own({"device_uuid": "REACH01"}, "device_uuid", "REACH01")["device_uuid"] == "REACH01"


def test_another_devices_identity_is_refused():
    with pytest.raises(PermissionDeniedError):
        _own({"device_id": "REACH02"}, "device_id", "REACH01")
    with pytest.raises(UnprocessableError):
        _own({"camera_id": "other"}, "camera_id", "front", what="camera")


def test_invalid_payload_gives_a_readable_error():
    with pytest.raises(UnprocessableError, match="invalid log: event_type"):
        _validate(EdgeLog, {"device_id": "REACH01"}, "log")


def test_reserved_and_oversized_logs_are_refused():
    reserved = EdgeLog.model_validate({"device_id": "R", "event_type": "system.connection"})
    assert "reserved" in EdgeLogService.rejection(reserved)
    big = EdgeLog.model_validate({"device_id": "R", "event_type": "x.y", "data": {"blob": "a" * 70_000}})
    assert "too large" in EdgeLogService.rejection(big)
    ok = EdgeLog.model_validate({"device_id": "R", "event_type": "office.leave"})
    assert EdgeLogService.rejection(ok) is None
