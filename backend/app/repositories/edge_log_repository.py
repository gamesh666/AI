from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.models.edge_device import EdgeDevice
from app.models.edge_log import EdgeLog
from app.repositories.base import BaseRepository
from app.schemas.edge_log import EdgeLogFilter

# fields a re-sent log replaces when the edge provides them (data is merged separately)
_UPDATABLE = ("severity", "status", "message", "detections", "frame", "snapshot_key", "camera_id", "camera_code")


class EdgeLogRepository(BaseRepository[EdgeLog]):
    model = EdgeLog

    def _with_relations(self):
        return select(EdgeLog).options(
            selectinload(EdgeLog.camera),
            selectinload(EdgeLog.edge_device).selectinload(EdgeDevice.site),
        )

    async def get_full(self, log_id) -> EdgeLog | None:
        stmt = self._with_relations().where(EdgeLog.id == log_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def list_stmt(self, f: EdgeLogFilter):
        stmt = self._with_relations().order_by(EdgeLog.occurred_at.desc())
        if f.start:
            stmt = stmt.where(EdgeLog.occurred_at >= f.start)
        if f.end:
            stmt = stmt.where(EdgeLog.occurred_at < f.end)
        if f.edge_device_id:
            stmt = stmt.where(EdgeLog.edge_device_id == f.edge_device_id)
        if f.camera_id:
            stmt = stmt.where(EdgeLog.camera_id == f.camera_id)
        if f.site_id:
            stmt = stmt.join(EdgeDevice, EdgeLog.edge_device_id == EdgeDevice.id).where(EdgeDevice.site_id == f.site_id)
        if f.event_type:
            stmt = stmt.where(EdgeLog.event_type == f.event_type)
        if f.severity:
            stmt = stmt.where(EdgeLog.severity == f.severity)
        if f.status:
            stmt = stmt.where(EdgeLog.status == f.status)
        if f.q:
            escaped = f.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            stmt = stmt.where(or_(EdgeLog.message.ilike(like), EdgeLog.event_id.ilike(like)))
        return stmt

    async def upsert(self, row: dict[str, Any], provided: set[str]) -> tuple[EdgeLog, bool]:
        """Insert, or update the existing (device, event_id) log. Returns (log, created).

        Only fields the edge actually sent are replaced; `data` is shallow-merged; occurred_at is kept.
        """
        stmt = pg_insert(EdgeLog).values(row)
        excluded = stmt.excluded
        updates: dict[str, Any] = {k: getattr(excluded, k) for k in _UPDATABLE if k in provided}
        updates["data"] = EdgeLog.data.op("||")(excluded.data)
        updates["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(constraint="uq_edge_logs_device_event", set_=updates).returning(
            EdgeLog.id, literal_column("(xmax = 0)")  # PostgreSQL: true when the row was inserted
        )
        log_id, created = (await self.session.execute(stmt)).one()
        log = (
            await self.session.execute(
                self._with_relations().where(EdgeLog.id == log_id).execution_options(populate_existing=True)
            )
        ).scalar_one()
        return log, bool(created)

    async def count_since(self, since: datetime) -> int:
        stmt = select(func.count()).select_from(EdgeLog).where(EdgeLog.occurred_at >= since)
        return (await self.session.execute(stmt)).scalar_one()

    async def distinct_types(self) -> list[str]:
        stmt = select(EdgeLog.event_type).distinct().order_by(EdgeLog.event_type)
        return list((await self.session.execute(stmt)).scalars().all())
