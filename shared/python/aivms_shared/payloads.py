"""MQTT payload contracts (Pydantic v2).

Both the backend (consumer) and the edge agent (producer) import these models,
so a contract change is a single edit here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()


# ---- heartbeat -------------------------------------------------------------


class Heartbeat(_Payload):
    device_uuid: str
    timestamp: datetime = Field(default_factory=utcnow)
    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)
    gpu_usage: float | None = Field(default=None, ge=0, le=100)
    gpu_memory_usage: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = None
    agent_version: str
    # optional static info, lets the server learn hardware without an extra call
    hostname: str | None = None
    ip_address: str | None = None
    gpu_name: str | None = None
    gpu_memory: int | None = Field(default=None, description="Total GPU memory in MB")


# ---- status ----------------------------------------------------------------


class DeviceState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class CameraState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class CameraStatus(_Payload):
    camera_id: str
    state: CameraState
    fps: float | None = None
    error: str | None = None


class DeviceStatus(_Payload):
    device_uuid: str
    timestamp: datetime = Field(default_factory=utcnow)
    state: DeviceState
    cameras: list[CameraStatus] = Field(default_factory=list)


# ---- detection -------------------------------------------------------------


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float = Field(ge=0, le=1)
    bbox: BBox


class DetectionEvent(_Payload):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    device_id: str
    camera_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    model: str
    detections: list[Detection]
    snapshot_key: str | None = Field(default=None, description="MinIO object key of the snapshot")
    frame_width: int | None = None
    frame_height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- server -> edge --------------------------------------------------------


class CommandType(StrEnum):
    RELOAD_CONFIG = "reload_config"
    RESTART_CAMERA = "restart_camera"
    CAPTURE_SNAPSHOT = "capture_snapshot"
    PING = "ping"


class Command(_Payload):
    command_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    command: CommandType
    params: dict[str, Any] = Field(default_factory=dict)
    issued_at: datetime = Field(default_factory=utcnow)


class ConfigChanged(_Payload):
    """Notification only. Config content (incl. RTSP credentials) is fetched over REST."""

    version: int
    changed_at: datetime = Field(default_factory=utcnow)
    reason: str | None = None


ALL_PAYLOADS: dict[str, type[BaseModel]] = {
    "heartbeat": Heartbeat,
    "device_status": DeviceStatus,
    "detection_event": DetectionEvent,
    "command": Command,
    "config_changed": ConfigChanged,
}
