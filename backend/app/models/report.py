from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A report the platform asked an edge to generate (heartbeat command); the edge uploads the PDF."""

    __tablename__ = "device_reports"

    edge_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="attendance")
    filters: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # queued -> generating -> ready | failed
    status: Mapped[str] = mapped_column(String(16), default="queued")
    message: Mapped[str | None] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(128))
    object_key: Mapped[str | None] = mapped_column(String(256))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
