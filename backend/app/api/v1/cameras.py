import uuid

from fastapi import APIRouter, status

from app.api.deps import DBSession, OperatorUser, Pagination, ViewerUser
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.schemas.common import Page
from app.services.camera_service import CameraService

router = APIRouter()


@router.get("", response_model=Page[CameraRead])
async def list_cameras(
    db: DBSession,
    _: ViewerUser,
    pagination: Pagination,
    site_id: uuid.UUID | None = None,
    edge_device_id: uuid.UUID | None = None,
    enabled: bool | None = None,
) -> Page[CameraRead]:
    return await CameraService(db).list(pagination, site_id, edge_device_id, enabled)


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
async def create_camera(body: CameraCreate, db: DBSession, _: OperatorUser) -> CameraRead:
    return await CameraService(db).create(body)


@router.get("/{camera_id}", response_model=CameraRead)
async def get_camera(camera_id: uuid.UUID, db: DBSession, _: ViewerUser) -> CameraRead:
    return await CameraService(db).get_read(camera_id)


@router.patch("/{camera_id}", response_model=CameraRead)
async def update_camera(camera_id: uuid.UUID, body: CameraUpdate, db: DBSession, _: OperatorUser) -> CameraRead:
    return await CameraService(db).update(camera_id, body)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: uuid.UUID, db: DBSession, _: OperatorUser) -> None:
    await CameraService(db).delete(camera_id)
