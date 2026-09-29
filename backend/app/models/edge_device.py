from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DeviceStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
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
    # extension: device authentication (sha256 of the device API key)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), unique=True)

    site: Mapped[Site | None] = relationship(back_populates="edge_devices")
    cameras: Mapped[list[Camera]] = relationship(
        back_populates="edge_device", cascade="all, delete-orphan"
    )
