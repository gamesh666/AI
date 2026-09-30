"""generic edge logs; edge-managed camera sources

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30

- edge_logs            any recognition result / log an edge reports (type and data are free-form)
- cameras.rtsp_url     nullable: NULL = the edge manages the camera source itself
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.alter_column("cameras", "rtsp_url", existing_type=sa.String(length=512), nullable=True)

    op.create_table(
        "edge_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("edge_device_id", sa.Uuid(), nullable=False),
        sa.Column("camera_id", sa.Uuid(), nullable=True),
        sa.Column("camera_code", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("data", JSON, nullable=False),
        sa.Column("detections", JSON, nullable=False),
        sa.Column("frame", JSON, nullable=True),
        sa.Column("snapshot_key", sa.String(length=512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["edge_device_id"], ["edge_devices.id"],
            name=op.f("fk_edge_logs_edge_device_id_edge_devices"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["camera_id"], ["cameras.id"], name=op.f("fk_edge_logs_camera_id_cameras"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edge_logs")),
        sa.UniqueConstraint("edge_device_id", "event_id", name="uq_edge_logs_device_event"),
    )
    op.create_index("ix_edge_logs_occurred_at", "edge_logs", ["occurred_at"])
    op.create_index("ix_edge_logs_device_time", "edge_logs", ["edge_device_id", "occurred_at"])
    op.create_index("ix_edge_logs_camera_time", "edge_logs", ["camera_id", "occurred_at"])
    op.create_index(op.f("ix_edge_logs_event_type"), "edge_logs", ["event_type"])
    op.create_index(op.f("ix_edge_logs_severity"), "edge_logs", ["severity"])


def downgrade() -> None:
    op.drop_table("edge_logs")
    op.execute("DELETE FROM cameras WHERE rtsp_url IS NULL")
    op.alter_column("cameras", "rtsp_url", existing_type=sa.String(length=512), nullable=False)
