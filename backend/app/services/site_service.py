from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.messaging import publisher
from app.models.edge_device import EdgeDevice
from app.models.site import Site
from app.repositories.site_repository import SiteRepository
from app.schemas.common import Page, PageParams
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services.camera_service import CameraService


class SiteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SiteRepository(session)

    async def list(self, params: PageParams) -> Page[SiteRead]:
        rows, total = await self.repo.paginate(self.repo.list_stmt(), params.offset, params.page_size)
        counts = await self.repo.device_counts([s.id for s in rows])
        items = []
        for site in rows:
            dto = SiteRead.model_validate(site)
            dto.device_count = counts.get(site.id, 0)
            items.append(dto)
        return Page(items=items, total=total, page=params.page, page_size=params.page_size)

    async def get(self, site_id: uuid.UUID) -> Site:
        site = await self.repo.get(site_id)
        if not site:
            raise NotFoundError("site not found")
        return site

    async def create(self, data: SiteCreate) -> Site:
        site = Site(**data.model_dump())
        try:
            await self.repo.add(site)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("site name or code already exists") from exc
        return site

    async def update(self, site_id: uuid.UUID, data: SiteUpdate) -> Site:
        site = await self.get(site_id)
        changes = data.model_dump(exclude_unset=True)
        code_changed = "code" in changes and changes["code"] != site.code
        self.repo.apply_updates(site, changes)
        devices = []
        try:
            if code_changed:
                await self.session.flush()
                devices = list((await self.session.execute(
                    select(EdgeDevice).where(EdgeDevice.site_id == site.id)
                )).scalars())
                cameras = CameraService(self.session)
                for device in devices:
                    await cameras.refresh_stream_paths(device)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("site name or code already exists") from exc
        for device in devices:
            await publisher.notify_config_changed(device.device_uuid, "site_code_changed")
        await self.session.refresh(site)
        return site

    async def delete(self, site_id: uuid.UUID) -> None:
        await self.repo.delete(await self.get(site_id))
        await self.session.commit()
