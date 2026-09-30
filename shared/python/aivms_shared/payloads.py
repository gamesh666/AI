"""MQTT payload contracts (Pydantic v2).

Both the backend (consumer) and the edge agent (producer) import these models,
so a contract change is a single edit here.

Video never travels over MQTT: these payloads carry metadata only. Annotated video is
an H.264 stream pushed from the edge to MediaMTX.
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


# ---- device status (edge/{device}/status, retained, also the MQTT Last Will) -----


class DeviceState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class DeviceStatus(_Payload):
    device_uuid: str
    timestamp: datetime = Field(default_factory=utcnow)
    state: DeviceState


# ---- per-camera health (edge/{device}/cameras/{camera}/status) --------------------


class RtspStatus(StrEnum):
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class AiStatus(StrEnum):
    DISABLED = "disabled"
    LOADING = "loading"
    RUNNING = "running"
    ERROR = "error"


class StreamStatus(StrEnum):
    OFFLINE = "offline"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ERROR = "error"


class CameraRuntimeStatus(_Payload):
    camera_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    rtsp_status: RtspStatus
    ai_status: AiStatus
    stream_status: StreamStatus
    input_fps: float = 0.0
    inference_fps: float = 0.0
    output_fps: float = 0.0
    resolution: str | None = Field(default=None, description="Source resolution, e.g. 1920x1080")
    last_frame_at: datetime | None = None
    dropped_frames: int = 0
    error: str | None = None


# ---- detection -------------------------------------------------------------


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    track_id: int | None = None
    class_id: int
    class_name: str
    confidence: float = Field(ge=0, le=1)
    bbox: BBox
    attributes: dict[str, Any] = Field(default_factory=dict)


class FrameInfo(BaseModel):
    width: int
    height: int


class DetectionEvent(_Payload):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    device_id: str
    camera_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    model: str
    frame: FrameInfo | None = None
    detections: list[Detection]
    snapshot_key: str | None = Field(default=None, description="MinIO object key of the annotated snapshot")
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- generic edge log -------------------------------------------------------

LOG_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}$"
LOG_TYPE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}$"


class LogSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EdgeLog(_Payload):
    """Anything an edge recognises or wants to report, whatever its AI does.

    The platform does not interpret `event_type` or `data`: it stores, filters and displays them.
    Re-sending the same `event_id` updates that log (e.g. a "leave" that later gets a return time):
    `status` / `message` / `severity` / `detections` / `snapshot_key` are replaced when given and
    `data` is shallow-merged, while the first `timestamp` is kept.
    """

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern=LOG_ID_PATTERN)
    device_id: str
    camera_id: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    event_type: str = Field(pattern=LOG_TYPE_PATTERN, description="free-form, e.g. office.leave, ppe.no_helmet")
    severity: LogSeverity = LogSeverity.INFO
    status: str | None = Field(default=None, max_length=32)
    message: str | None = Field(default=None, max_length=1000)
    data: dict[str, Any] = Field(default_factory=dict)
    detections: list[Detection] = Field(default_factory=list, max_length=200)
    frame: FrameInfo | None = None
    snapshot_key: str | None = Field(default=None, max_length=512)


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
    "camera_status": CameraRuntimeStatus,
    "detection_event": DetectionEvent,
    "edge_log": EdgeLog,
    "command": Command,
    "config_changed": ConfigChanged,
}
