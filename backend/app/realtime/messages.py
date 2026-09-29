"""Realtime message envelope pushed to browsers over WebSocket."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RealtimeEventType(StrEnum):
    DETECTION_CREATED = "detection.created"
    DEVICE_HEARTBEAT = "device.heartbeat"
    DEVICE_STATUS = "device.status"
    CAMERA_STATUS = "camera.status"


class RealtimeMessage(BaseModel):
    type: RealtimeEventType
    data: dict[str, Any]
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
