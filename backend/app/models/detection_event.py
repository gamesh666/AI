from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_model import AIModel
    from app.models.camera import Camera
    from app.models.edge_device import EdgeDevice


class DetectionEvent(UUIDPrimaryKeyMixin, Base):
    """One row per detected object. A single MQTT message (event_group_id) may produce many rows."""

    __tablename__ = "detection_events"
    __table_args__ = (
        UniqueConstraint("event_group_id", "detection_index", name="uq_detection_events_group_index"),
        Index("ix_detection_events_detected_at", "detected_at"),
        Index("ix_detection_events_camera_time", "camera_id", "detected_at"),
        Index("ix_detection_events_device_time", "edge_device_id", "detected_at"),
    )

    event_group_id: Mapped[uuid.UUID] = mapped_column(index=True)
    detection_index: Mapped[int] = mapped_column(Integer, default=0)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    edge_device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE")
    )
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    class_name: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    bbox: Mapped[dict[str, float]] = mapped_column(JSONType)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # MinIO object key; converted to a presigned URL when served
    snapshot_url: Mapped[str | None] = mapped_column(String(512))
    # "metadata" is reserved by SQLAlchemy's declarative API -> attribute name differs from column
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped[Camera] = relationship()
    edge_device: Mapped[EdgeDevice] = relationship()
    ai_model: Mapped[AIModel | None] = relationship()
