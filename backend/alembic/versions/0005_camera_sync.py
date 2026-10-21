"""camera list sync from edges

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12

- cameras.missing_from_edge_at   set when an edge-managed camera is no longer in the edge's camera list
                                 (the camera is disabled, never deleted); cleared when the edge lists it again
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("missing_from_edge_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "missing_from_edge_at")
