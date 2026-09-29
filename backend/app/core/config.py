"""Application settings. Every secret comes from environment variables — nothing is hardcoded."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- app ---
    app_name: str = "AI VMS Backend"
    environment: str = Field(default="development", alias="APP_ENV")
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    # comma separated list
    cors_origins: str = "http://localhost:3000"

    # --- database ---
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "aivms"
    postgres_user: str = "aivms"
    postgres_password: SecretStr
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- auth ---
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    stream_token_expire_seconds: int = 300

    # --- initial admin (created by seed on first start) ---
    initial_admin_username: str = "admin"
    initial_admin_password: SecretStr | None = None
    initial_admin_email: str | None = None
    # creates a demo site / edge device / synthetic camera (for the `edge` compose profile)
    seed_demo_data: bool = False
    demo_device_uuid: str = "edge-demo-001"

    # --- credentials encryption (RTSP passwords) ---
    credential_encryption_key: SecretStr

    # --- edge provisioning ---
    edge_provisioning_token: SecretStr
    device_offline_after_seconds: int = 30
    device_monitor_interval_seconds: int = 10

    # --- mqtt ---
    mqtt_enabled: bool = True
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    mqtt_username: str = "backend"
    mqtt_password: SecretStr
    mqtt_client_id_prefix: str = "aivms-backend"
    mqtt_shared_group: str | None = "backend"
    mqtt_tls: bool = False
    # address edge agents use to reach the broker (returned in /edge/config)
    mqtt_public_host: str = "localhost"
    mqtt_public_port: int = 1883

    # --- minio ---
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: SecretStr
    minio_secure: bool = False
    minio_region: str = "us-east-1"
    minio_bucket_snapshots: str = "snapshots"
    # URL browsers use to download presigned snapshots
    minio_public_url: str = "http://localhost:9000"
    # URL edge agents use to upload snapshots
    minio_edge_url: str = "http://localhost:9000"
    snapshot_url_expire_seconds: int = 3600

    # --- mediamtx ---
    mediamtx_webrtc_public_url: str = "http://localhost:8889"
    mediamtx_hls_public_url: str = "http://localhost:8888"
    # address edge agents publish RTSP to
    mediamtx_rtsp_publish_url: str = "rtsp://localhost:8554"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{quote(self.postgres_user)}:{quote(self.postgres_password.get_secret_value())}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
