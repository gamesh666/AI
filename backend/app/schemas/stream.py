from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class StreamInfo(BaseModel):
    camera_id: uuid.UUID
    stream_id: str
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
