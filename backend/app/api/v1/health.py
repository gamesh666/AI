from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.redis import get_redis

router = APIRouter()


@router.get("/health")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: DBSession) -> JSONResponse:
    checks: dict[str, bool] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    try:
        checks["redis"] = bool(await get_redis().ping())
    except Exception:
        checks["redis"] = False
    ok = checks["database"] and checks["redis"]
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "checks": checks},
    )
