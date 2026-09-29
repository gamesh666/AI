"""Subset of the backend's /edge/config response the agent relies on."""

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


class CameraConfig(_M):
    id: str
    name: str
    rtsp_url: str
    onvif_url: str | None = None
    stream_id: str
    enabled: bool = True
    ai_enabled: bool = True
    ai_model: ModelConfig | None = None

    def fingerprint(self) -> tuple:
        """Anything that requires restarting the camera worker when changed."""
        return (self.rtsp_url, self.stream_id, self.enabled, self.ai_enabled,
                self.ai_model.id if self.ai_model else None)


class MQTTConfig(_M):
    host: str
    port: int
    tls: bool = False


class StreamingConfig(_M):
    rtsp_publish_url: str


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
