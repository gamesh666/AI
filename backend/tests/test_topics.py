from aivms_shared import topics
from aivms_shared.topics import TopicKind
from app.messaging.mqtt_broker import topic_matches


def test_builders_and_parse_roundtrip():
    assert topics.heartbeat("edge-001") == "edge/edge-001/heartbeat"
    assert topics.camera_events("edge-001", "cam-1") == "edge/edge-001/cameras/cam-1/events"
    assert topics.command("edge-001") == "server/edge-001/command"

    p = topics.parse("edge/edge-001/cameras/cam-1/events")
    assert p is not None and p.kind == TopicKind.CAMERA_EVENTS and p.camera_id == "cam-1"
    assert topics.parse("edge/edge-001/heartbeat").kind == TopicKind.HEARTBEAT
    status = topics.parse(topics.camera_status("edge01", "cam01"))
    assert status is not None and status.kind == TopicKind.CAMERA_STATUS and status.camera_id == "cam01"
    assert topics.parse("edge/edge01/cameras/cam01/other") is None
    assert topics.parse("edge/edge-001/unknown") is None
    assert topics.parse("edge//heartbeat") is None


def test_shared_subscription():
    assert topics.shared("edge/+/heartbeat", "backend") == "$share/backend/edge/+/heartbeat"
    assert topics.shared("edge/+/heartbeat", None) == "edge/+/heartbeat"


def test_topic_matching_with_share_prefix():
    f = "$share/backend/edge/+/cameras/+/events"
    assert topic_matches(f, "edge/e1/cameras/c1/events")
    assert not topic_matches(f, "edge/e1/events")
    assert topic_matches("edge/+/events", "edge/e1/events")
    assert not topic_matches("edge/+/events", "edge/e1/cameras/c1/events")
    assert topic_matches("edge/#", "edge/e1/cameras/c1/events")
