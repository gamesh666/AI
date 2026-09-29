"""Edge agent settings: environment variables (EDGE_*) override an optional YAML file (EDGE_CONFIG_FILE)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class _YamlSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        path = os.environ.get("EDGE_CONFIG_FILE")
        self._data: dict[str, Any] = {}
        if path and Path(path).is_file():
            self._data = yaml.safe_load(Path(path).read_text()) or {}

    def get_field_value(self, field, field_name):  # pragma: no cover - required by the ABC
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if k in self.settings_cls.model_fields}


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDGE_", extra="ignore")

    # identity
    device_uuid: str = Field(pattern=r"^[A-Za-z0-9_\-]{3,64}$")
    device_name: str | None = None
    data_dir: Path = Path("/var/lib/aivms-edge")

    # central REST API
    api_url: str = "http://localhost:8000/api/v1"
    api_timeout_seconds: float = 10.0
    provisioning_token: SecretStr | None = None
    # optional pre-provisioned key (otherwise obtained via /edge/register and cached in data_dir)
    device_key: SecretStr | None = None

    # MQTT (host/port fall back to what the server returns in /edge/config)
    mqtt_host: str | None = None
    mqtt_port: int | None = None
    mqtt_username: str | None = None
    mqtt_password: SecretStr | None = None
    mqtt_tls: bool = False
    mqtt_keepalive: int = 30
    mqtt_max_queued_messages: int = 5000

    # streaming
    stream_relay_enabled: bool = True
    rtsp_publish_url: str | None = None
    ffmpeg_path: str = "ffmpeg"

    # inference
    detector: str = "mock"  # mock | yolo
    inference_fps: float = 2.0
    min_confidence: float = 0.5
    event_cooldown_seconds: float = 5.0
    mock_detection_probability: float = 0.15

    # snapshots
    snapshot_enabled: bool = True
    snapshot_jpeg_quality: int = 80

    # telemetry
    heartbeat_interval_seconds: float = 10.0
    status_interval_seconds: float = 30.0
    config_poll_interval_seconds: float = 300.0

    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, _YamlSource(settings_cls), file_secret_settings


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()  # type: ignore[call-arg]
