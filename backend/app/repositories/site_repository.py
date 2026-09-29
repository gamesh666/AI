from __future__ import annotations

from sqlalchemy import func, select

from app.models.edge_device import EdgeDevice
from app.models.site import Site
from app.repositories.base import BaseRepository


class SiteRepository(BaseRepository[Site]):
    model = Site

    def list_stmt(self):
        return select(Site).order_by(Site.name)

    async def device_counts(self, site_ids: list) -> dict:
        if not site_ids:
            return {}
        stmt = (
            select(EdgeDevice.site_id, func.count())
            .where(EdgeDevice.site_id.in_(site_ids))
            .group_by(EdgeDevice.site_id)
        )
        return dict((await self.session.execute(stmt)).all())
