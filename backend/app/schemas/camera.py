from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.enums import CameraStatus, StreamStatus
from app.schemas.common import ORMModel
from app.schemas.site import SLUG_PATTERN

RESOLUTION_PATTERN = r"^\d{2,5}x\d{2,5}$"
BITRATE_PATTERN = r"^\d+(\.\d+)?[kKmM]?$"


_SOURCE_URL = re.compile(r"^[a-z][a-z0-9+.\-]*://\S+$")


def _validate_rtsp(v: str | None) -> str | None:
    """Any source URL the edge understands (rtsp://, rtsps://, or a scheme added by an edge plugin).

    The platform only stores and forwards it; which schemes are supported is decided on the edge.
    """
    if v and not _SOURCE_URL.match(v):
        raise ValueError("rtsp_url must be a URL such as rtsp://host:554/stream")
    return v


class _StreamSettings(BaseModel):
    stream_enabled: bool | None = None
    annotated_stream_enabled: bool | None = None
    original_stream_enabled: bool | None = None
    resolution: str | None = Field(default=None, pattern=RESOLUTION_PATTERN)
    stream_fps: int | None = Field(default=None, ge=1, le=60)
    inference_fps: float | None = Field(default=None, gt=0, le=60)
    bitrate: str | None = Field(default=None, pattern=BITRATE_PATTERN)
    gop_size: int | None = Field(default=None, ge=1, le=600)


class CameraCreate(_StreamSettings):
    edge_device_id: uuid.UUID
    code: str = Field(pattern=SLUG_PATTERN, description="Unique per edge device, e.g. cam01")
    name: str = Field(min_length=1, max_length=128)
    # write-only. Credentials may be embedded (rtsp://user:pass@host/...) or given separately;
    # either way they are stripped from the URL and stored encrypted.
    # None = the edge manages the camera source itself (e.g. a third-party edge)
    rtsp_url: str | None = Field(default=None, max_length=512)
    rtsp_username: str | None = Field(default=None, max_length=128)
    rtsp_password: str | None = Field(default=None, max_length=256)
    onvif_url: str | None = Field(default=None, max_length=512)
    enabled: bool = True
    ai_enabled: bool = True
    ai_model_id: uuid.UUID | None = None

    _check_rtsp = field_validator("rtsp_url")(_validate_rtsp)


class CameraUpdate(_StreamSettings):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    code: str | None = Field(default=None, pattern=SLUG_PATTERN)
    # empty string clears the source (and its credentials): the edge manages it
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
    """Public camera representation.

    Contains NO camera address, RTSP URL or credentials: those are edge-site internals.
    """

    id: uuid.UUID
    code: str
    edge_device_id: uuid.UUID
    edge_device_uuid: str | None = None
    edge_device_name: str | None = None
    edge_device_status: str | None = None
    site_id: uuid.UUID | None = None
    site_code: str | None = None
    site_name: str | None = None
    name: str
    source_configured: bool
    has_credentials: bool
    enabled: bool
    ai_enabled: bool
    stream_enabled: bool
    annotated_stream_enabled: bool
    original_stream_enabled: bool
    ai_model_id: uuid.UUID | None
    ai_model_name: str | None = None
    stream_path: str
    resolution: str | None
    stream_fps: int
    inference_fps: float
    bitrate: str
    gop_size: int
    status: CameraStatus
    stream_status: StreamStatus
    ai_status: str
    last_frame_at: datetime | None
    runtime_stats: dict[str, Any]
    created_at: datetime
