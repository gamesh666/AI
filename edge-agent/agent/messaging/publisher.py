"""Typed publishing of the shared telemetry contracts (MQTT, or HTTP via agent.messaging.http_publisher)."""

from __future__ import annotations

from typing import Protocol

from agent.messaging.mqtt import EdgeMQTTClient
from aivms_shared import topics
from aivms_shared.payloads import CameraRuntimeStatus, DetectionEvent, DeviceState, DeviceStatus, Heartbeat


class TelemetryPublisher(Protocol):
    @property
    def ready(self) -> bool: ...
    def heartbeat(self, hb: Heartbeat) -> None: ...
    def status(self, status: DeviceStatus) -> None: ...
    def camera_status(self, status: CameraRuntimeStatus) -> None: ...
    def detection(self, event: DetectionEvent) -> None: ...


class SwitchablePublisher:
    """What pipelines and the heartbeat hold, so the transport can change (MQTT -> HTTP) while running."""

    def __init__(self, target: TelemetryPublisher) -> None:
        self.target = target

    @property
    def ready(self) -> bool:
        return self.target.ready

    def heartbeat(self, hb: Heartbeat) -> None:
        self.target.heartbeat(hb)

    def status(self, status: DeviceStatus) -> None:
        self.target.status(status)

    def camera_status(self, status: CameraRuntimeStatus) -> None:
        self.target.camera_status(status)

    def detection(self, event: DetectionEvent) -> None:
        self.target.detection(event)


class EdgePublisher:
    def __init__(self, client: EdgeMQTTClient, device_uuid: str) -> None:
        self._client = client
        self._device = device_uuid

    @property
    def ready(self) -> bool:
        return self._client.connected

    def configure_last_will(self) -> None:
        will = DeviceStatus(device_uuid=self._device, state=DeviceState.OFFLINE)
        self._client.set_will(topics.status(self._device), will.to_bytes(), qos=1, retain=True)

    def heartbeat(self, hb: Heartbeat) -> None:
        self._client.publish(topics.heartbeat(self._device), hb.to_bytes(), qos=0)

    def status(self, status: DeviceStatus) -> None:
        self._client.publish(topics.status(self._device), status.to_bytes(), qos=1, retain=True)

    def camera_status(self, status: CameraRuntimeStatus) -> None:
        topic = topics.camera_status(self._device, status.camera_id)
        self._client.publish(topic, status.to_bytes(), qos=0)

    def detection(self, event: DetectionEvent) -> None:
        topic = topics.camera_events(self._device, event.camera_id)
        self._client.publish(topic, event.to_bytes(), qos=1)
