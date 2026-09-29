"""Typed publishing of the shared MQTT contracts."""

from __future__ import annotations

from agent.messaging.mqtt_client import EdgeMQTTClient
from aivms_shared import topics
from aivms_shared.payloads import DetectionEvent, DeviceState, DeviceStatus, Heartbeat


class EdgePublisher:
    def __init__(self, client: EdgeMQTTClient, device_uuid: str) -> None:
        self._client = client
        self._device = device_uuid

    def configure_last_will(self) -> None:
        will = DeviceStatus(device_uuid=self._device, state=DeviceState.OFFLINE)
        self._client.set_will(topics.status(self._device), will.to_bytes(), qos=1, retain=True)

    def heartbeat(self, hb: Heartbeat) -> None:
        self._client.publish(topics.heartbeat(self._device), hb.to_bytes(), qos=0)

    def status(self, status: DeviceStatus) -> None:
        self._client.publish(topics.status(self._device), status.to_bytes(), qos=1, retain=True)

    def detection(self, event: DetectionEvent) -> None:
        topic = topics.camera_events(self._device, event.camera_id)
        self._client.publish(topic, event.to_bytes(), qos=1)
