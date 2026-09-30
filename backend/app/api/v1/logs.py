"""Edge logs: whatever the edges recognise or report, stored and shown as-is."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DBSession, Pagination, ViewerUser
from app.schemas.common import Page
from app.schemas.edge_log import EdgeLogFilter, EdgeLogRead
from app.services.edge_log_service import EdgeLogService

router = APIRouter()


@router.get("", response_model=Page[EdgeLogRead])
async def list_logs(
    db: DBSession,
    _: ViewerUser,
    pagination: Pagination,
    start: datetime | None = None,
    end: datetime | None = None,
    site_id: uuid.UUID | None = None,
    edge_device_id: uuid.UUID | None = None,
    camera_id: uuid.UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    q: str | None = None,
) -> Page[EdgeLogRead]:
    filters = EdgeLogFilter(
        start=start, end=end, site_id=site_id, edge_device_id=edge_device_id, camera_id=camera_id,
        event_type=event_type, severity=severity, status=status_, q=q,
    )
    return await EdgeLogService(db).list(pagination, filters)


@router.get("/types", response_model=list[str])
async def list_log_types(db: DBSession, _: ViewerUser) -> list[str]:
    return await EdgeLogService(db).types()


@router.get("/{log_id}", response_model=EdgeLogRead)
async def get_log(log_id: uuid.UUID, db: DBSession, _: ViewerUser) -> EdgeLogRead:
    return await EdgeLogService(db).get(log_id)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(log_id: uuid.UUID, db: DBSession, _: AdminUser) -> None:
    await EdgeLogService(db).delete(log_id)
