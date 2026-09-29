import uuid

from fastapi import APIRouter, status

from app.api.deps import DBSession, OperatorUser, Pagination, ViewerUser
from app.schemas.common import Page
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services.site_service import SiteService

router = APIRouter()


@router.get("", response_model=Page[SiteRead])
async def list_sites(db: DBSession, _: ViewerUser, pagination: Pagination) -> Page[SiteRead]:
    return await SiteService(db).list(pagination)


@router.post("", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
async def create_site(body: SiteCreate, db: DBSession, _: OperatorUser) -> SiteRead:
    return SiteRead.model_validate(await SiteService(db).create(body))


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(site_id: uuid.UUID, db: DBSession, _: ViewerUser) -> SiteRead:
    return SiteRead.model_validate(await SiteService(db).get(site_id))


@router.patch("/{site_id}", response_model=SiteRead)
async def update_site(site_id: uuid.UUID, body: SiteUpdate, db: DBSession, _: OperatorUser) -> SiteRead:
    return SiteRead.model_validate(await SiteService(db).update(site_id, body))


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site_id: uuid.UUID, db: DBSession, _: OperatorUser) -> None:
    await SiteService(db).delete(site_id)
