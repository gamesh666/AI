"""platform-generated logs (connection history, platform start/stop)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07

- edge_logs.edge_device_id nullable: platform-level records (e.g. system.platform) belong to no device
- index for "open connection record of a device" lookups
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("edge_logs", "edge_device_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index("ix_edge_logs_type_status", "edge_logs", ["event_type", "status"])


def downgrade() -> None:
    op.drop_index("ix_edge_logs_type_status", table_name="edge_logs")
    op.execute("DELETE FROM edge_logs WHERE edge_device_id IS NULL")
    op.alter_column("edge_logs", "edge_device_id", existing_type=sa.Uuid(), nullable=False)
