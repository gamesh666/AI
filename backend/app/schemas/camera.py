from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.enums import CameraStatus
from app.schemas.common import ORMModel


def _validate_rtsp(v: str | None) -> str | None:
    if v is not None and not v.startswith(("rtsp://", "rtsps://", "mock://")):
        raise ValueError("rtsp_url must start with rtsp://, rtsps:// or mock://")
    return v


class CameraCreate(BaseModel):
    edge_device_id: uuid.UUID
    name: str = Field(min_length=1, max_length=128)
    # credentials may be embedded (rtsp://user:pass@host/...) or given separately;
    # either way they are stripped from the URL and stored encrypted.
    rtsp_url: str = Field(max_length=512)
    rtsp_username: str | None = Field(default=None, max_length=128)
    rtsp_password: str | None = Field(default=None, max_length=256)
    onvif_url: str | None = Field(default=None, max_length=512)
    stream_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_\-]{2,63}$")
    enabled: bool = True
    ai_enabled: bool = True
    ai_model_id: uuid.UUID | None = None

    _check_rtsp = field_validator("rtsp_url")(_validate_rtsp)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    rtsp_url: str | None = Field(default=None, max_length=512)
    rtsp_username: str | None = Field(default=None, max_length=128)
    # empty string clears the password
    rtsp_password: str | None = Field(default=None, max_length=256)
    onvif_url: str | None = Field(default=None, max_length=512)
    enabled: bool | None = None
    ai_enabled: bool | None = None
    ai_model_id: uuid.UUID | None = None
    edge_device_id: uuid.UUID | None = None

    _check_rtsp = field_validator("rtsp_url")(_validate_rtsp)


class CameraRead(ORMModel):
    """Public camera representation. NEVER contains RTSP credentials."""

    id: uuid.UUID
    edge_device_id: uuid.UUID
    edge_device_name: str | None = None
    edge_device_status: str | None = None
    site_id: uuid.UUID | None = None
    site_name: str | None = None
    name: str
    rtsp_url_masked: str
    has_credentials: bool
    onvif_url: str | None
    stream_id: str
    enabled: bool
    ai_enabled: bool
    ai_model_id: uuid.UUID | None
    ai_model_name: str | None = None
    status: CameraStatus
    created_at: datetime
