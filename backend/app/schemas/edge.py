"""Schemas for the device-facing (edge agent) REST API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.edge_device import DEVICE_UUID_PATTERN


class EdgeRegisterRequest(BaseModel):
    device_uuid: str = Field(pattern=DEVICE_UUID_PATTERN)
    name: str | None = Field(default=None, max_length=128)
    hostname: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None
    gpu_name: str | None = None
    gpu_memory: int | None = None


class EdgeRegisterResponse(BaseModel):
    id: uuid.UUID
    device_uuid: str
    api_key: str


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
    camera_id: str  # camera code, used in MQTT topics and payloads
    name: str
    # full URL WITH credentials — only served to the owning, authenticated device over HTTPS
    rtsp_url: str
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


class EdgeMQTTConfig(BaseModel):
    host: str
    port: int
    tls: bool
    topics: dict[str, str]


class EdgeStreamingConfig(BaseModel):
    protocol: str = "rtsp"  # rtsp | srt
    rtsp_publish_url: str
    srt_publish_url: str | None = None


class EdgeConfig(BaseModel):
    device_uuid: str
    version: int
    heartbeat_interval_seconds: int = 10
    cameras: list[EdgeCameraConfig]
    mqtt: EdgeMQTTConfig
    streaming: EdgeStreamingConfig


class PresignRequest(BaseModel):
    camera_id: uuid.UUID
    content_type: str = "image/jpeg"


class PresignResponse(BaseModel):
    object_key: str
    upload_url: str
    expires_in: int
