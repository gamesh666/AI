from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.edge_device import EdgeDevice


class EdgeLog(UUIDPrimaryKeyMixin, Base):
    """A recognition result / log line reported by an edge, whatever its AI does.

    The platform does not interpret event_type or data. (edge_device_id, event_id) identifies a log,
    so an edge can update it later (e.g. status open -> closed).
    """

    __tablename__ = "edge_logs"
    __table_args__ = (
        UniqueConstraint("edge_device_id", "event_id", name="uq_edge_logs_device_event"),
        Index("ix_edge_logs_occurred_at", "occurred_at"),
        Index("ix_edge_logs_device_time", "edge_device_id", "occurred_at"),
        Index("ix_edge_logs_camera_time", "camera_id", "occurred_at"),
        Index("ix_edge_logs_type_status", "event_type", "status"),
    )

    event_id: Mapped[str] = mapped_column(String(64))
    # NULL = a platform-level record (e.g. system.platform)
    edge_device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("edge_devices.id", ondelete="CASCADE"))
    camera_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    # camera code as reported, kept even if the camera is not (or no longer) registered
    camera_code: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    detections: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    frame: Mapped[dict[str, int] | None] = mapped_column(JSONType)
    # MinIO object key; converted to a presigned URL when served
    snapshot_key: Mapped[str | None] = mapped_column(String(512))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped[Camera | None] = relationship()
    edge_device: Mapped[EdgeDevice | None] = relationship()
