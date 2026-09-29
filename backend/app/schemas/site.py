from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteRead(ORMModel):
    id: uuid.UUID
    name: str
    address: str | None
    description: str | None
    created_at: datetime
    device_count: int = 0
