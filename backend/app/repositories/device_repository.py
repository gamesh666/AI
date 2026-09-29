from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.core.enums import DeviceStatus
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[EdgeDevice]):
    model = EdgeDevice

    async def get_by_device_uuid(self, device_uuid: str) -> EdgeDevice | None:
        return await self.get_by(device_uuid=device_uuid)

    async def get_by_api_key_hash(self, key_hash: str) -> EdgeDevice | None:
        return await self.get_by(api_key_hash=key_hash)

    def list_stmt(self, site_id: uuid.UUID | None = None, status: DeviceStatus | None = None):
        stmt = select(EdgeDevice).options(selectinload(EdgeDevice.site)).order_by(EdgeDevice.name)
        if site_id:
            stmt = stmt.where(EdgeDevice.site_id == site_id)
        if status:
            stmt = stmt.where(EdgeDevice.status == status)
        return stmt

    async def camera_counts(self, device_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not device_ids:
            return {}
        stmt = (
            select(Camera.edge_device_id, func.count())
            .where(Camera.edge_device_id.in_(device_ids))
            .group_by(Camera.edge_device_id)
        )
        return dict((await self.session.execute(stmt)).all())

    async def mark_stale_offline(self, cutoff: datetime) -> list[EdgeDevice]:
        """Set status=offline for online devices not seen since `cutoff`; returns affected rows."""
        stmt = (
            update(EdgeDevice)
            .where(EdgeDevice.status == DeviceStatus.ONLINE, EdgeDevice.last_seen < cutoff)
            .values(status=DeviceStatus.OFFLINE)
            .returning(EdgeDevice.id, EdgeDevice.device_uuid)
        )
        return list((await self.session.execute(stmt)).all())

    async def count_by_status(self) -> dict[DeviceStatus, int]:
        stmt = select(EdgeDevice.status, func.count()).group_by(EdgeDevice.status)
        return dict((await self.session.execute(stmt)).all())
