"""HTTP-only edges: drop the MQTT-era detection table and transport tracking

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-21

- detection_events               edge-agent detections; every recognition result is an Edge log now
- edge_devices.last_mqtt_at / last_http_at   MQTT -> HTTP cut-over tracking, done
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("detection_events")
    op.drop_column("edge_devices", "last_mqtt_at")
    op.drop_column("edge_devices", "last_http_at")


def downgrade() -> None:
    op.add_column("edge_devices", sa.Column("last_http_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("edge_devices", sa.Column("last_mqtt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table('detection_events',
    sa.Column('event_group_id', sa.Uuid(), nullable=False),
    sa.Column('detection_index', sa.Integer(), nullable=False),
    sa.Column('camera_id', sa.Uuid(), nullable=False),
    sa.Column('edge_device_id', sa.Uuid(), nullable=False),
    sa.Column('ai_model_id', sa.Uuid(), nullable=True),
    sa.Column('class_name', sa.String(length=64), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('bbox', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('snapshot_url', sa.String(length=512), nullable=True),
    sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['ai_model_id'], ['ai_models.id'], name=op.f('fk_detection_events_ai_model_id_ai_models'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], name=op.f('fk_detection_events_camera_id_cameras'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['edge_device_id'], ['edge_devices.id'], name=op.f('fk_detection_events_edge_device_id_edge_devices'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_detection_events')),
    sa.UniqueConstraint('event_group_id', 'detection_index', name='uq_detection_events_group_index')
    )
    op.create_index('ix_detection_events_camera_time', 'detection_events', ['camera_id', 'detected_at'], unique=False)
    op.create_index(op.f('ix_detection_events_class_name'), 'detection_events', ['class_name'], unique=False)
    op.create_index('ix_detection_events_detected_at', 'detection_events', ['detected_at'], unique=False)
    op.create_index('ix_detection_events_device_time', 'detection_events', ['edge_device_id', 'detected_at'], unique=False)
    op.create_index(op.f('ix_detection_events_event_group_id'), 'detection_events', ['event_group_id'], unique=False)
