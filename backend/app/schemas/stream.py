from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from app.core.enums import StreamStatus, StreamType


class StreamInfo(BaseModel):
    """Everything a browser needs to play a camera — and nothing about the camera itself."""

    camera_id: uuid.UUID
    camera_code: str
    status: StreamStatus
    stream_type: StreamType
    webrtc_url: str
    hls_url: str
    token: str
    expires_in: int


class MediaMTXAuthRequest(BaseModel):
    """Body sent by MediaMTX when authMethod=http."""

    user: str | None = None
    password: str | None = None
    token: str | None = None
    ip: str | None = None
    action: str
    path: str | None = None
    protocol: str | None = None
    id: str | None = None
    query: str | None = None

    model_config = {"extra": "allow"}

    def extra_fields(self) -> dict[str, Any]:
        return self.model_extra or {}
