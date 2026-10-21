"""Schemas for the device-facing (edge agent) REST API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.site import SLUG_PATTERN


class EdgeRegisterResponse(BaseModel):
    """Fixed by the REACH AI BOX register contract (§3.5)."""

    api_key: str
    device_uuid: str
    site_id: str = ""  # site code, "" when the device has no site
    site_profile: dict[str, Any] | None = None


class EdgeSiteProfileResponse(BaseModel):
    site_profile: dict[str, Any] | None = None


class EdgeModelConfig(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    model_type: str
    labels: list[str]
    model_path: str


class EdgeVideoConfig(BaseModel):
    video_codec: str = "h264"
    width: int | None = None  # None = keep source resolution
    height: int | None = None
    stream_fps: int = 25
    inference_fps: float = 5.0
    bitrate: str = "2M"
    gop_size: int = 50


class EdgeCameraConfig(BaseModel):
    id: uuid.UUID
    camera_id: str  # camera code, used in API paths, logs and stream paths
    name: str
    # full URL WITH credentials — only served to the owning, authenticated device over HTTPS.
    # None = the edge manages this camera's source itself.
    rtsp_url: str | None
    onvif_url: str | None
    enabled: bool
    ai_enabled: bool
    stream_enabled: bool
    annotated_stream_enabled: bool
    original_stream_enabled: bool
    stream_path: str
    original_stream_path: str
    video: EdgeVideoConfig
    ai_model: EdgeModelConfig | None


class EdgeStreamingConfig(BaseModel):
    protocol: str = "rtsp"  # rtsp | srt
    rtsp_publish_url: str
    srt_publish_url: str | None = None


class EdgeTelemetryConfig(BaseModel):
    """Where to send heartbeat / status / logs (POST with X-Device-Key)."""

    # always false: there is no MQTT any more (kept so edges that check it keep working)
    mqtt_enabled: bool = False
    # API paths, relative to the API base URL
    http: dict[str, str]


class EdgeConfig(BaseModel):
    device_uuid: str
    site_id: str = ""  # site code, "" when the device has no site
    version: int
    heartbeat_interval_seconds: int = 10
    cameras: list[EdgeCameraConfig]
    telemetry: EdgeTelemetryConfig
    streaming: EdgeStreamingConfig
    # owner / site / contract data (REACH register contract §3.6); None when unknown
    site_profile: dict[str, Any] | None = None


class PresignRequest(BaseModel):
    # either the camera UUID (from /edge/config) or its code; neither = device-level snapshot
    camera_id: uuid.UUID | None = None
    camera_code: str | None = Field(default=None, max_length=64)
    content_type: str = "image/jpeg"


class EdgeCameraDeclare(BaseModel):
    """A camera an edge announces itself (its source stays on the edge)."""

    name: str | None = Field(default=None, min_length=1, max_length=128)


class EdgeCameraListItem(EdgeCameraDeclare):
    code: str = Field(pattern=SLUG_PATTERN)


class EdgeCameraSync(BaseModel):
    """The edge's COMPLETE camera list. Edge-managed cameras not in it are disabled (never deleted)."""

    cameras: list[EdgeCameraListItem] = Field(max_length=256)

    @field_validator("cameras")
    @classmethod
    def _unique_codes(cls, v: list[EdgeCameraListItem]) -> list[EdgeCameraListItem]:
        codes = [c.code for c in v]
        if len(codes) != len(set(codes)):
            raise ValueError("camera codes must be unique")
        return v


class EdgeCameraSyncResult(BaseModel):
    cameras: list[EdgeCameraConfig]  # the listed cameras, with the stream path to publish to
    added: list[str]
    restored: list[str]  # listed again after having been missing -> re-enabled
    missing: list[str]  # newly missing -> disabled


class PresignResponse(BaseModel):
    object_key: str
    upload_url: str
    expires_in: int


class EdgeHeartbeatAck(BaseModel):
    """Answer to POST /edge/heartbeat: what the platform has for the edge."""

    # changes whenever the platform-side config changes; re-fetch GET /edge/config when it differs from the last
    config_version: int
    # pending commands (oldest first), each {command_id, command, params, issued_at}; delivered once
    commands: list[dict[str, Any]] = Field(default_factory=list)
    # always false: there is no MQTT any more (kept so edges that check it keep working)
    mqtt_enabled: bool = False
    server_time: datetime


class EdgeLogAck(BaseModel):
    event_id: str
    camera_id: str | None = None


class EdgeLogRejected(BaseModel):
    index: int
    detail: str


class EdgeLogBatchAck(BaseModel):
    accepted: list[EdgeLogAck]
    rejected: list[EdgeLogRejected]
