from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.models.detection_event import DetectionEvent
from app.models.edge_device import EdgeDevice
from app.repositories.base import BaseRepository
from app.schemas.detection_event import EventFilter


class EventRepository(BaseRepository[DetectionEvent]):
    model = DetectionEvent

    def _with_relations(self):
        return select(DetectionEvent).options(
            selectinload(DetectionEvent.camera),
            selectinload(DetectionEvent.edge_device).selectinload(EdgeDevice.site),
            selectinload(DetectionEvent.ai_model),
        )

    async def get_full(self, event_id) -> DetectionEvent | None:
        stmt = self._with_relations().where(DetectionEvent.id == event_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def list_stmt(self, f: EventFilter):
        stmt = self._with_relations().order_by(DetectionEvent.detected_at.desc())
        if f.start:
            stmt = stmt.where(DetectionEvent.detected_at >= f.start)
        if f.end:
            stmt = stmt.where(DetectionEvent.detected_at < f.end)
        if f.camera_id:
            stmt = stmt.where(DetectionEvent.camera_id == f.camera_id)
        if f.edge_device_id:
            stmt = stmt.where(DetectionEvent.edge_device_id == f.edge_device_id)
        if f.site_id:
            stmt = stmt.join(EdgeDevice, DetectionEvent.edge_device_id == EdgeDevice.id).where(
                EdgeDevice.site_id == f.site_id
            )
        if f.class_name:
            stmt = stmt.where(DetectionEvent.class_name == f.class_name)
        if f.min_confidence is not None:
            stmt = stmt.where(DetectionEvent.confidence >= f.min_confidence)
        if f.max_confidence is not None:
            stmt = stmt.where(DetectionEvent.confidence <= f.max_confidence)
        return stmt

    async def insert_many_idempotent(self, rows: list[dict[str, Any]]) -> list[DetectionEvent]:
        """Insert rows, silently skipping duplicates (QoS1 redelivery). Returns inserted rows."""
        if not rows:
            return []
        stmt = (
            pg_insert(DetectionEvent)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_detection_events_group_index")
            .returning(DetectionEvent.id)
        )
        ids = list((await self.session.execute(stmt)).scalars().all())
        if not ids:
            return []
        result = await self.session.execute(self._with_relations().where(DetectionEvent.id.in_(ids)))
        return list(result.scalars().all())

    async def count_since(self, since: datetime) -> int:
        stmt = select(func.count()).select_from(DetectionEvent).where(DetectionEvent.detected_at >= since)
        return (await self.session.execute(stmt)).scalar_one()

    async def distinct_classes(self) -> list[str]:
        stmt = select(DetectionEvent.class_name).distinct().order_by(DetectionEvent.class_name)
        return list((await self.session.execute(stmt)).scalars().all())


