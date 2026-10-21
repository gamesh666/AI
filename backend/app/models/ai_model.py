from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class AIModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ai_models_name_version"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32))
    model_type: Mapped[str] = mapped_column(String(32))  # yolov8 / yolo11 / onnx / tensorrt ...
    labels: Mapped[list[str]] = mapped_column(JSONType, default=list)
    model_path: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
