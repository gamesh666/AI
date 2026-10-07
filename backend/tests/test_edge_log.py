import pytest
from pydantic import ValidationError

from aivms_shared import topics
from aivms_shared.payloads import EdgeLog, LogSeverity
from aivms_shared.topics import TopicKind


def test_log_topics_are_parsed():
    assert topics.parse("edge/REACH01/logs") == topics.ParsedTopic(TopicKind.DEVICE_LOGS, "REACH01")
    assert topics.parse("edge/REACH01/cameras/bimer-back-left/logs") == topics.ParsedTopic(
        TopicKind.CAMERA_LOGS, "REACH01", "bimer-back-left"
    )
    assert topics.camera_logs("d", "c") == "edge/d/cameras/c/logs"
    assert TopicKind.DEVICE_LOGS in topics.SERVER_SUBSCRIPTIONS
    assert TopicKind.CAMERA_LOGS in topics.SERVER_SUBSCRIPTIONS


def test_minimal_log_gets_defaults():
    log = EdgeLog.model_validate({"device_id": "REACH01", "event_type": "office.leave"})
    assert log.severity is LogSeverity.INFO
    assert log.event_id and log.data == {} and log.detections == []


def test_free_form_data_and_detections_are_accepted():
    log = EdgeLog.model_validate(
        {
            "event_id": "leave-2026-09-30-S01-1",
            "device_id": "REACH01",
            "camera_id": "bimer-back-left",
            "event_type": "office.leave",
            "severity": "warning",
            "status": "open",
            "message": "S01 away",
            "data": {"seat_id": "S01", "nested": {"a": [1, 2]}},
            "detections": [{"class_id": 0, "class_name": "person", "confidence": 0.9,
                            "bbox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}],
            "unknown_field": "ignored",
        }
    )
    assert log.data["nested"] == {"a": [1, 2]}
    assert "unknown_field" not in log.model_dump()
    # only what the edge sent is replaced on an update
    assert {"status", "message", "data", "detections"} <= log.model_fields_set
    assert "snapshot_key" not in log.model_fields_set


@pytest.mark.parametrize(
    "field,value",
    [("event_type", "has space"), ("event_type", ""), ("event_id", "../x"), ("severity", "fatal")],
)
def test_invalid_values_are_rejected(field, value):
    body = {"device_id": "d", "event_type": "ok.type", field: value}
    with pytest.raises(ValidationError):
        EdgeLog.model_validate(body)


async def test_platform_event_types_cannot_be_sent_by_edges():
    from app.services.connection_history import CONNECTION, PLATFORM
    from app.services.edge_log_service import RESERVED_EVENT_TYPES, EdgeLogService

    assert {CONNECTION, PLATFORM} == RESERVED_EVENT_TYPES
    forged = EdgeLog.model_validate({"device_id": "d", "event_type": CONNECTION, "status": "recovered"})
    # rejected before any database access (the session is never touched)
    assert await EdgeLogService(session=None).ingest(forged, "d") is None  # type: ignore[arg-type]
