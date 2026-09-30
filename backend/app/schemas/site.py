from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# site / camera IDs used in stream paths, e.g. site01, CAM001
SLUG_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_\-]{1,31}$"


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(pattern=SLUG_PATTERN, description="Slug used in stream paths, e.g. site01")
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    code: str | None = Field(default=None, pattern=SLUG_PATTERN)
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    description: str | None
    created_at: datetime
    device_count: int = 0
