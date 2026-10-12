"""models reported by edges

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-12

- edge_devices.reported_models     models the edge says it is running (heartbeat), incl. which cameras use them
- edge_devices.reported_models_at  when that list was last reported
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("edge_devices", sa.Column("reported_models", JSON, nullable=True))
    op.add_column("edge_devices", sa.Column("reported_models_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("edge_devices", "reported_models_at")
    op.drop_column("edge_devices", "reported_models")
