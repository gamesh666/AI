"""Device-facing API used by edge agents (authenticated with X-Device-Key)."""

from typing import Annotated

from fastapi import APIRouter, Header, Path

from app.api.deps import CurrentDevice, DBSession
from app.core.exceptions import AuthError
from app.schemas.edge import (
    EdgeCameraConfig,
    EdgeCameraDeclare,
    EdgeConfig,
    EdgeRegisterRequest,
    EdgeRegisterResponse,
    PresignRequest,
    PresignResponse,
)
from app.schemas.site import SLUG_PATTERN
from app.services.device_service import DeviceService
from app.services.edge_service import EdgeService

router = APIRouter()


@router.post("/register", response_model=EdgeRegisterResponse)
async def register(
    body: EdgeRegisterRequest,
    db: DBSession,
    x_provisioning_token: Annotated[str | None, Header()] = None,
) -> EdgeRegisterResponse:
    if not x_provisioning_token:
        raise AuthError("missing X-Provisioning-Token")
    device, api_key = await DeviceService(db).register(body, x_provisioning_token)
    return EdgeRegisterResponse(id=device.id, device_uuid=device.device_uuid, api_key=api_key)


@router.get("/config", response_model=EdgeConfig)
async def get_config(device: CurrentDevice, db: DBSession) -> EdgeConfig:
    return await EdgeService(db).build_config(device)


@router.post("/snapshots/presign", response_model=PresignResponse)
async def presign_snapshot(body: PresignRequest, device: CurrentDevice, db: DBSession) -> PresignResponse:
    return await EdgeService(db).presign_snapshot(device, body.camera_id, body.camera_code)


@router.put("/cameras/{code}", response_model=EdgeCameraConfig)
async def declare_camera(
    body: EdgeCameraDeclare,
    device: CurrentDevice,
    db: DBSession,
    code: Annotated[str, Path(pattern=SLUG_PATTERN)],
) -> EdgeCameraConfig:
    """For edges that manage their own cameras: announce one so its logs and live stream show up.

    Idempotent. Returns the camera's platform config, including the stream path to publish to.
    """
    return await EdgeService(db).declare_camera(device, code, body.name)
