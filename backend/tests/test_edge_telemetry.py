import pytest

from aivms_shared.payloads import EdgeLog
from app.api.v1.edge_telemetry import _own, _validate
from app.core.exceptions import PermissionDeniedError
from app.services.edge_log_service import EdgeLogService
from app.services.provisioning import UnprocessableError


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
