"""Configuration served by the backend (GET /edge/config). Mirrors backend/app/schemas/edge.py."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ModelConfig(_M):
    id: str
    name: str
    version: str
    model_type: str
    labels: list[str] = []
    model_path: str


class VideoConfig(_M):
    video_codec: str = "h264"
    width: int | None = None  # None = keep source resolution
    height: int | None = None
    stream_fps: int = 25
    inference_fps: float = 5.0
    bitrate: str = "2M"
    gop_size: int = 50


class CameraConfig(_M):
    id: str  # backend UUID (REST calls)
    camera_id: str  # camera code (MQTT topics / payloads)
    name: str
    rtsp_url: str
    onvif_url: str | None = None
    enabled: bool = True
    ai_enabled: bool = True
    stream_enabled: bool = True
    annotated_stream_enabled: bool = True
    original_stream_enabled: bool = False
    stream_path: str  # ai/<site>/<device>/<camera>
    original_stream_path: str  # original/<site>/<device>/<camera>
    video: VideoConfig = VideoConfig()
    ai_model: ModelConfig | None = None

    def fingerprint(self) -> str:
        """Any change requires rebuilding this camera's pipeline."""
        return self.model_dump_json()


class MQTTConfig(_M):
    host: str
    port: int
    tls: bool = False


class StreamingConfig(_M):
    protocol: str = "rtsp"
    rtsp_publish_url: str
    srt_publish_url: str | None = None


class DeviceConfig(_M):
    device_uuid: str
    version: int
    heartbeat_interval_seconds: int = 10
    cameras: list[CameraConfig] = []
    mqtt: MQTTConfig
    streaming: StreamingConfig


class PresignedUpload(_M):
    object_key: str
    upload_url: str
    expires_in: int
