from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EdgeLogFilter(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    site_id: uuid.UUID | None = None
    edge_device_id: uuid.UUID | None = None
    camera_id: uuid.UUID | None = None
    event_type: str | None = None
    severity: str | None = None
    status: str | None = None
    q: str | None = Field(default=None, max_length=200, description="substring of message / event_id")


class EdgeLogRead(BaseModel):
    id: uuid.UUID
    event_id: str
    edge_device_id: uuid.UUID | None = None
    edge_device_uuid: str | None = None
    edge_device_name: str | None = None
    site_id: uuid.UUID | None = None
    site_name: str | None = None
    camera_id: uuid.UUID | None = None
    camera_code: str | None = None
    camera_name: str | None = None
    event_type: str
    severity: str
    status: str | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    detections: list[dict[str, Any]] = Field(default_factory=list)
    frame: dict[str, int] | None = None
    snapshot_url: str | None = Field(default=None, description="Presigned download URL")
    occurred_at: datetime
    updated_at: datetime
