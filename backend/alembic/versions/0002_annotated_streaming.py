"""annotated streaming: site/camera codes, stream paths, stream settings and health

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

- sites.code                         slug used in stream paths
- cameras.code / stream_path         ai/<site>/<device>/<camera> replaces stream_id
- cameras stream/encoding settings   stream_enabled, annotated/original switches, fps, bitrate, gop
- cameras runtime health             stream_status, ai_status, last_frame_at, runtime_stats
- detection_events.track_id
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
stream_status = postgresql.ENUM("offline", "connecting", "streaming", "error", name="stream_status", create_type=False)


def upgrade() -> None:
    # camera_status gains "connecting" (safe inside a transaction on PostgreSQL >= 12 as long as it is unused here)
    op.execute("ALTER TYPE camera_status ADD VALUE IF NOT EXISTS 'connecting'")
    stream_status.create(op.get_bind(), checkfirst=True)

    # ---- sites.code ---------------------------------------------------------
    op.add_column("sites", sa.Column("code", sa.String(length=32), nullable=True))
    op.execute("UPDATE sites SET code = 'site-' || substr(replace(id::text, '-', ''), 1, 8)")
    op.alter_column("sites", "code", nullable=False)
    op.create_unique_constraint(op.f("uq_sites_code"), "sites", ["code"])

    # ---- cameras --------------------------------------------------------------
    op.add_column("cameras", sa.Column("code", sa.String(length=32), nullable=True))
    op.add_column("cameras", sa.Column("stream_path", sa.String(length=255), nullable=True))
    op.execute("UPDATE cameras SET code = left(stream_id, 32)")
    op.execute(
        """
        UPDATE cameras c
        SET stream_path = 'ai/' || coalesce(s.code, 'unassigned') || '/' || d.device_uuid || '/' || c.code
        FROM edge_devices d LEFT JOIN sites s ON s.id = d.site_id
        WHERE d.id = c.edge_device_id
        """
    )
    op.alter_column("cameras", "code", nullable=False)
    op.alter_column("cameras", "stream_path", nullable=False)
    op.create_unique_constraint("uq_cameras_device_code", "cameras", ["edge_device_id", "code"])
    op.create_unique_constraint(op.f("uq_cameras_stream_path"), "cameras", ["stream_path"])
    op.drop_index(op.f("ix_cameras_stream_id"), table_name="cameras")
    op.drop_column("cameras", "stream_id")

    columns = [
        sa.Column("stream_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("annotated_stream_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("original_stream_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("stream_fps", sa.Integer(), server_default="25", nullable=False),
        sa.Column("inference_fps", sa.Float(), server_default="5", nullable=False),
        sa.Column("video_codec", sa.String(length=16), server_default="h264", nullable=False),
        sa.Column("bitrate", sa.String(length=16), server_default="2M", nullable=False),
        sa.Column("gop_size", sa.Integer(), server_default="50", nullable=False),
        sa.Column("stream_status", stream_status, server_default="offline", nullable=False),
        sa.Column("ai_status", sa.String(length=16), server_default="idle", nullable=False),
        sa.Column("last_frame_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runtime_stats", JSON, server_default=sa.text("'{}'::jsonb"), nullable=False),
    ]
    for column in columns:
        op.add_column("cameras", column)

    # ---- detection_events.track_id ------------------------------------------------
    op.add_column("detection_events", sa.Column("track_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("detection_events", "track_id")

    for name in ("runtime_stats", "last_frame_at", "ai_status", "stream_status", "gop_size", "bitrate",
                 "video_codec", "inference_fps", "stream_fps", "resolution", "original_stream_enabled",
                 "annotated_stream_enabled", "stream_enabled"):
        op.drop_column("cameras", name)

    op.add_column("cameras", sa.Column("stream_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE cameras SET stream_id = code")
    op.alter_column("cameras", "stream_id", nullable=False)
    op.create_index(op.f("ix_cameras_stream_id"), "cameras", ["stream_id"], unique=True)
    op.drop_constraint(op.f("uq_cameras_stream_path"), "cameras", type_="unique")
    op.drop_constraint("uq_cameras_device_code", "cameras", type_="unique")
    op.drop_column("cameras", "stream_path")
    op.drop_column("cameras", "code")

    op.drop_constraint(op.f("uq_sites_code"), "sites", type_="unique")
    op.drop_column("sites", "code")

    stream_status.drop(op.get_bind(), checkfirst=True)
    # PostgreSQL cannot drop a single enum value; camera_status keeps "connecting" (harmless)
