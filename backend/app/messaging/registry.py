"""Builds the broker and wires topic filters to handlers."""

from __future__ import annotations

from aivms_shared import topics
from aivms_shared.topics import TopicKind
from app.core.config import Settings
from app.messaging.base import MessageBroker
from app.messaging.handlers.camera_status import handle_camera_status
from app.messaging.handlers.detection import handle_detection
from app.messaging.handlers.heartbeat import handle_heartbeat
from app.messaging.handlers.status import handle_status
from app.messaging.mqtt_broker import MQTTBroker

HANDLERS = {
    TopicKind.HEARTBEAT: (handle_heartbeat, 0),
    TopicKind.STATUS: (handle_status, 1),
    TopicKind.DEVICE_EVENTS: (handle_detection, 1),
    TopicKind.CAMERA_EVENTS: (handle_detection, 1),
    TopicKind.CAMERA_STATUS: (handle_camera_status, 0),
}


def build_broker(settings: Settings) -> MessageBroker:
    broker = MQTTBroker(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password.get_secret_value(),
        client_id_prefix=settings.mqtt_client_id_prefix,
        tls=settings.mqtt_tls,
    )
    for kind, topic_filter in topics.SERVER_SUBSCRIPTIONS.items():
        handler, qos = HANDLERS[kind]
        broker.subscribe(topics.shared(topic_filter, settings.mqtt_shared_group), handler, qos)
    return broker
