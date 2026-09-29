from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CameraStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_model import AIModel
    from app.models.edge_device import EdgeDevice


class Camera(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cameras"

    edge_device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    # stored WITHOUT credentials; credentials live in the columns below
    rtsp_url: Mapped[str] = mapped_column(String(512))
    rtsp_username: Mapped[str | None] = mapped_column(String(128))
    rtsp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    onvif_url: Mapped[str | None] = mapped_column(String(512))
    stream_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    status: Mapped[CameraStatus] = mapped_column(
        Enum(CameraStatus, name="camera_status", values_callable=lambda e: [m.value for m in e]),
        default=CameraStatus.UNKNOWN,
    )

    edge_device: Mapped[EdgeDevice] = relationship(back_populates="cameras")
    ai_model: Mapped[AIModel | None] = relationship()
