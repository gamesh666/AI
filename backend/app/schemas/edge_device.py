from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import DeviceStatus
from app.schemas.common import ORMModel

DEVICE_UUID_PATTERN = r"^[A-Za-z0-9_\-]{3,64}$"


class EdgeDeviceCreate(BaseModel):
    device_uuid: str = Field(pattern=DEVICE_UUID_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    site_id: uuid.UUID | None = None


class EdgeDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    site_id: uuid.UUID | None = None


class EdgeDeviceRead(ORMModel):
    id: uuid.UUID
    device_uuid: str
    name: str
    site_id: uuid.UUID | None
    site_name: str | None = None
    hostname: str | None
    ip_address: str | None
    status: DeviceStatus
    last_seen: datetime | None
    agent_version: str | None
    gpu_name: str | None
    gpu_memory: int | None
    cpu_usage: float | None
    memory_usage: float | None
    gpu_usage: float | None
    gpu_memory_usage: float | None
    temperature: float | None
    camera_count: int = 0
    created_at: datetime


class EdgeConnectionInfo(BaseModel):
    """Everything an edge needs to connect, except the device key (shown once, separately)."""

    device_id: str
    mqtt_host: str
    mqtt_port: int
    mqtt_tls: bool
    mqtt_username: str
    # only for admins; None = ask an administrator
    mqtt_password: str | None = None
    stream_protocol: str
    rtsp_publish_url: str
    srt_publish_url: str | None = None
    snapshot_upload_url: str
    topics: dict[str, str]


class EdgeDeviceWithKey(EdgeDeviceRead):
    """Returned only once, when a device is created / its key is rotated."""

    api_key: str
    connection: EdgeConnectionInfo | None = None


class DeviceCommandRequest(BaseModel):
    command: str
    params: dict = Field(default_factory=dict)
