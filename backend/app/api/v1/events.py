import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DBSession, Pagination, ViewerUser
from app.schemas.common import Page
from app.schemas.detection_event import DetectionEventRead, EventFilter
from app.services.event_service import EventService

router = APIRouter()


@router.get("", response_model=Page[DetectionEventRead])
async def list_events(
    db: DBSession,
    _: ViewerUser,
    pagination: Pagination,
    start: datetime | None = None,
    end: datetime | None = None,
    site_id: uuid.UUID | None = None,
    camera_id: uuid.UUID | None = None,
    edge_device_id: uuid.UUID | None = None,
    class_name: str | None = None,
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
    max_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
) -> Page[DetectionEventRead]:
    filters = EventFilter(
        start=start, end=end, site_id=site_id, camera_id=camera_id, edge_device_id=edge_device_id,
        class_name=class_name, min_confidence=min_confidence, max_confidence=max_confidence,
    )
    return await EventService(db).list(pagination, filters)


@router.get("/classes", response_model=list[str])
async def list_event_classes(db: DBSession, _: ViewerUser) -> list[str]:
    return await EventService(db).classes()


@router.get("/{event_id}", response_model=DetectionEventRead)
async def get_event(event_id: uuid.UUID, db: DBSession, _: ViewerUser) -> DetectionEventRead:
    return await EventService(db).get(event_id)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: uuid.UUID, db: DBSession, _: AdminUser) -> None:
    await EventService(db).delete(event_id)
