from datetime import datetime

from fastapi import APIRouter

from app.api.deps import DBSession, ViewerUser
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary(db: DBSession, _: ViewerUser, since: datetime | None = None) -> DashboardSummary:
    return await DashboardService(db).summary(since)
