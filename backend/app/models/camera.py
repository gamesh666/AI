from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CameraStatus, StreamStatus
from app.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_model import AIModel
    from app.models.edge_device import EdgeDevice


def _enum(enum_cls, name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Camera(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A camera is identified by site / edge device / camera code — never by its IP address.

    site_id is derived from edge_device.site_id (not stored twice, so it cannot drift).
    """

    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("edge_device_id", "code", name="uq_cameras_device_code"),)

    edge_device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    # slug unique per edge device, used as camera_id in MQTT and in stream paths ("cam01")
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))

    # ---- source (edge-side only; never returned to the frontend) ----
    rtsp_url: Mapped[str] = mapped_column(String(512))  # stored WITHOUT credentials
    rtsp_username: Mapped[str | None] = mapped_column(String(128))
    rtsp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    onvif_url: Mapped[str | None] = mapped_column(String(512))

    # ---- switches ----
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    stream_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    annotated_stream_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    original_stream_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"))

    # ---- stream / encoding settings ----
    # MediaMTX path of the annotated stream: ai/<site>/<device>/<camera>
    stream_path: Mapped[str] = mapped_column(String(255), unique=True)
    resolution: Mapped[str | None] = mapped_column(String(16))  # "1920x1080"; NULL = source resolution
    stream_fps: Mapped[int] = mapped_column(Integer, default=25)
    inference_fps: Mapped[float] = mapped_column(Float, default=5.0)
    video_codec: Mapped[str] = mapped_column(String(16), default="h264")
    bitrate: Mapped[str] = mapped_column(String(16), default="2M")
    gop_size: Mapped[int] = mapped_column(Integer, default=50)

    # ---- runtime health (reported by the edge) ----
    status: Mapped[CameraStatus] = mapped_column(_enum(CameraStatus, "camera_status"), default=CameraStatus.UNKNOWN)
    stream_status: Mapped[StreamStatus] = mapped_column(
        _enum(StreamStatus, "stream_status"), default=StreamStatus.OFFLINE
    )
    ai_status: Mapped[str] = mapped_column(String(16), default="idle")
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime_stats: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    edge_device: Mapped[EdgeDevice] = relationship(back_populates="cameras")
    ai_model: Mapped[AIModel | None] = relationship()

    @property
    def original_stream_path(self) -> str:
        return "original/" + self.stream_path.split("/", 1)[1]
