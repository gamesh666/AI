from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AIModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    model_type: str = Field(default="yolov8", max_length=32)
    labels: list[str] = Field(default_factory=list)
    model_path: str = Field(max_length=512)
    description: str | None = None


class AIModelUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=32)
    model_type: str | None = Field(default=None, max_length=32)
    labels: list[str] | None = None
    model_path: str | None = Field(default=None, max_length=512)
    description: str | None = None


class AIModelRead(ORMModel):
    id: uuid.UUID
    name: str
    version: str
    model_type: str
    labels: list[str]
    model_path: str
    description: str | None
    created_at: datetime
