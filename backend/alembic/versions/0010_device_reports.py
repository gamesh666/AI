"""Reports generated on the edge (PDF uploaded back), report choices sent by the edge

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27

- device_reports                       one row per "產生報表" request
- edge_devices.report_options(_at)     employees / departments / seats... for the report dialog
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("edge_devices", sa.Column("report_options", postgresql.JSONB(), nullable=True))
    op.add_column("edge_devices", sa.Column("report_options_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "device_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("edge_device_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("message", sa.String(512), nullable=True),
        sa.Column("filename", sa.String(128), nullable=False),
        sa.Column("object_key", sa.String(256), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["edge_device_id"], ["edge_devices.id"],
                                name="fk_device_reports_edge_device_id_edge_devices", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"],
                                name="fk_device_reports_requested_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_device_reports"),
    )
    op.create_index("ix_device_reports_edge_device_id", "device_reports", ["edge_device_id"])


def downgrade() -> None:
    op.drop_index("ix_device_reports_edge_device_id", table_name="device_reports")
    op.drop_table("device_reports")
    op.drop_column("edge_devices", "report_options_at")
    op.drop_column("edge_devices", "report_options")
