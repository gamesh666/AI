"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging
from app.core.redis import close_redis
from app.db.session import dispose_engine
from app.messaging.registry import build_broker
from app.messaging.runtime import set_broker
from app.realtime.broadcaster import broadcaster
from app.realtime.router import router as ws_router
from app.services import storage_service
from app.workers.device_monitor import DeviceMonitor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    monitor = DeviceMonitor()
    if placeholders := settings.placeholder_secrets():
        logger.warning("placeholder secrets in use (development only!): %s — run ./scripts/generate-secrets.sh",
                       ", ".join(placeholders))

    try:
        await storage_service.ensure_buckets()
    except Exception:
        logger.exception("MinIO not reachable at startup; snapshots unavailable until it is")

    broadcaster.start()
    monitor.start()

    broker = None
    if settings.mqtt_enabled:
        broker = build_broker(settings)
        set_broker(broker)
        await broker.start()

    logger.info("%s started (env=%s)", settings.app_name, settings.environment)
    try:
        yield
    finally:
        if broker:
            await broker.stop()
            set_broker(None)
        await monitor.stop()
        await broadcaster.stop()
        await close_redis()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message}, headers=headers)

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    return app


app = create_app()
