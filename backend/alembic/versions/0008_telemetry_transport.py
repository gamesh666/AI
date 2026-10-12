"""telemetry over HTTP: remember which transport each edge uses

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-12

- edge_devices.last_mqtt_at / last_http_at   last heartbeat per transport (MQTT cut-over readiness)
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("edge_devices", sa.Column("last_mqtt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("edge_devices", sa.Column("last_http_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("edge_devices", "last_http_at")
    op.drop_column("edge_devices", "last_mqtt_at")
