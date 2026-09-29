from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class EventFilter(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    site_id: uuid.UUID | None = None
    camera_id: uuid.UUID | None = None
    edge_device_id: uuid.UUID | None = None
    class_name: str | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    max_confidence: float | None = Field(default=None, ge=0, le=1)


class DetectionEventRead(ORMModel):
    id: uuid.UUID
    event_group_id: uuid.UUID
    camera_id: uuid.UUID
    camera_name: str | None = None
    edge_device_id: uuid.UUID
    edge_device_name: str | None = None
    site_id: uuid.UUID | None = None
    site_name: str | None = None
    ai_model_id: uuid.UUID | None
    ai_model_name: str | None = None
    class_name: str
    confidence: float
    bbox: dict[str, float]
    detected_at: datetime
    snapshot_url: str | None = Field(default=None, description="Presigned download URL")
    metadata: dict[str, Any] = Field(default_factory=dict)
