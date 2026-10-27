from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.enums import DeviceStatus
from app.schemas.common import ORMModel

DEVICE_UUID_PATTERN = r"^[A-Za-z0-9_\-]{3,64}$"


class EdgeDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    site_id: uuid.UUID | None = None
    # admin only
    mac_address: str | None = Field(default=None, max_length=32)  # "" clears
    owner_id: uuid.UUID | None = None
    admin_state: Literal["active", "disabled", "retired"] | None = None


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
    # connection losses in the last 24 h (connection history)
    disconnects_24h: int = 0
    mac_address: str | None = None
    admin_state: str = "active"
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    registered_at: datetime | None = None
    last_registered_at: datetime | None = None
    # models the edge reports running (heartbeat), None = never reported
    reported_models: list[dict[str, Any]] | None = None
    reported_models_at: datetime | None = None
    created_at: datetime


class DeviceCommandRequest(BaseModel):
    command: str
    params: dict = Field(default_factory=dict)
