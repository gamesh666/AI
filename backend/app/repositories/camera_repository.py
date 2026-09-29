from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.enums import CameraStatus, DeviceStatus
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    model = Camera

    def _with_relations(self):
        return select(Camera).options(
            selectinload(Camera.edge_device).selectinload(EdgeDevice.site),
            selectinload(Camera.ai_model),
        )

    async def get_full(self, camera_id: uuid.UUID) -> Camera | None:
        stmt = self._with_relations().where(Camera.id == camera_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_stream_path(self, stream_path: str) -> Camera | None:
        """Lookup by the annotated stream path (ai/<site>/<device>/<camera>)."""
        stmt = self._with_relations().where(Camera.stream_path == stream_path)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_device_code(self, edge_device_id: uuid.UUID, code: str) -> Camera | None:
        stmt = self._with_relations().where(Camera.edge_device_id == edge_device_id, Camera.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def list_stmt(
        self,
        site_id: uuid.UUID | None = None,
        edge_device_id: uuid.UUID | None = None,
        enabled: bool | None = None,
    ):
        stmt = self._with_relations().order_by(Camera.name)
        if site_id:
            stmt = stmt.join(EdgeDevice, Camera.edge_device_id == EdgeDevice.id).where(
                EdgeDevice.site_id == site_id
            )
        if edge_device_id:
            stmt = stmt.where(Camera.edge_device_id == edge_device_id)
        if enabled is not None:
            stmt = stmt.where(Camera.enabled == enabled)
        return stmt

    async def list_for_device(self, edge_device_id: uuid.UUID) -> list[Camera]:
        stmt = self._with_relations().where(Camera.edge_device_id == edge_device_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_total(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(Camera))).scalar_one()

    async def count_active(self) -> int:
        """Enabled cameras that are streaming on an online device."""
        stmt = (
            select(func.count())
            .select_from(Camera)
            .join(EdgeDevice, Camera.edge_device_id == EdgeDevice.id)
            .where(
                Camera.enabled.is_(True),
                Camera.status == CameraStatus.ONLINE,
                EdgeDevice.status == DeviceStatus.ONLINE,
            )
        )
        return (await self.session.execute(stmt)).scalar_one()
