from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.site import Site
from app.repositories.site_repository import SiteRepository
from app.schemas.common import Page, PageParams
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate


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
            raise ConflictError("site name already exists") from exc
        return site

    async def update(self, site_id: uuid.UUID, data: SiteUpdate) -> Site:
        site = self.repo.apply_updates(await self.get(site_id), data.model_dump(exclude_unset=True))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("site name already exists") from exc
        await self.session.refresh(site)
        return site

    async def delete(self, site_id: uuid.UUID) -> None:
        await self.repo.delete(await self.get(site_id))
        await self.session.commit()
