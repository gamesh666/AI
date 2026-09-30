from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DeviceStatus
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.edge_log_repository import EdgeLogRepository
from app.repositories.event_repository import EventRepository
from app.schemas.dashboard import DashboardSummary


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.devices = DeviceRepository(session)
        self.cameras = CameraRepository(session)
        self.events = EventRepository(session)
        self.logs = EdgeLogRepository(session)

    async def summary(self, since: datetime | None = None) -> DashboardSummary:
        """`since` lets the client pass its local midnight; defaults to UTC midnight."""
        if since is None:
            since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        by_status = await self.devices.count_by_status()
        return DashboardSummary(
            online_devices=by_status.get(DeviceStatus.ONLINE, 0),
            offline_devices=by_status.get(DeviceStatus.OFFLINE, 0),
            pending_devices=by_status.get(DeviceStatus.PENDING, 0),
            camera_count=await self.cameras.count_total(),
            active_camera_count=await self.cameras.count_active(),
            events_today=await self.events.count_since(since),
            logs_today=await self.logs.count_since(since),
        )
