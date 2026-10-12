from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DeviceStatus
from app.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.owner import Owner
    from app.models.site import Site


class EdgeDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "edge_devices"

    device_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), index=True
    )
    hostname: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status", values_callable=lambda e: [m.value for m in e]),
        default=DeviceStatus.PENDING,
        index=True,
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_version: Mapped[str | None] = mapped_column(String(32))
    gpu_name: Mapped[str | None] = mapped_column(String(128))
    gpu_memory: Mapped[int | None] = mapped_column(Integer)  # MB
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    memory_usage: Mapped[float | None] = mapped_column(Float)
    # extension: fields carried by heartbeat
    gpu_usage: Mapped[float | None] = mapped_column(Float)
    gpu_memory_usage: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)
    # models the edge reports running (heartbeat `models`), NULL = never reported
    reported_models: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    reported_models_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # extension: device authentication (sha256 of the device API key)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    # ---- provisioning (REACH register contract) ----
    mac_address: Mapped[str | None] = mapped_column(String(17), unique=True)  # aa:bb:cc:dd:ee:ff
    admin_state: Mapped[str] = mapped_column(String(16), default="active")  # active | disabled | retired
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("owners.id", ondelete="SET NULL"), index=True)
    provisioning_token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provisioning_tokens.id", ondelete="SET NULL")
    )
    # when telemetry (heartbeat) last arrived over each transport; tells when MQTT can be switched off
    last_mqtt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_http_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    site: Mapped[Site | None] = relationship(back_populates="edge_devices")
    owner: Mapped[Owner | None] = relationship()
    cameras: Mapped[list[Camera]] = relationship(
        back_populates="edge_device", cascade="all, delete-orphan"
    )
