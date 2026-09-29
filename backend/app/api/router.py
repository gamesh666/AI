from fastapi import APIRouter

from app.api.v1 import (
    ai_models,
    auth,
    cameras,
    dashboard,
    devices,
    edge,
    events,
    health,
    sites,
    streams,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(devices.router, prefix="/devices", tags=["edge-devices"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["cameras"])
api_router.include_router(ai_models.router, prefix="/ai-models", tags=["ai-models"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(streams.router, prefix="/streams", tags=["streams"])
api_router.include_router(edge.router, prefix="/edge", tags=["edge-agent"])
