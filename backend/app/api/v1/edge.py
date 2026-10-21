"""Device-facing API used by edge agents (authenticated with X-Device-Key)."""

from typing import Annotated

from fastapi import APIRouter, Header, Path, Request

from app.api.deps import CurrentDevice, DBSession
from app.schemas.edge import (
    EdgeCameraConfig,
    EdgeCameraDeclare,
    EdgeCameraSync,
    EdgeCameraSyncResult,
    EdgeConfig,
    EdgeRegisterResponse,
    EdgeSiteProfileResponse,
    PresignRequest,
    PresignResponse,
)
from app.schemas.site import SLUG_PATTERN
from app.services.edge_service import EdgeService
from app.services.provisioning import (
    ProvisioningService,
    UnprocessableError,
    check_rate_limit,
    device_site_profile,
)

router = APIRouter()


@router.post("/register", response_model=EdgeRegisterResponse, response_model_exclude_none=False)
async def register(
    request: Request,
    db: DBSession,
    x_provisioning_token: Annotated[str | None, Header()] = None,
) -> EdgeRegisterResponse:
    """Edge self-registration.

    REACH AI BOX contract: owner provisioning token, identity = MAC, platform-assigned device ID, the key is
    rotated on every call, `site_profile` is returned.
    Errors are always {"detail": "<text>"}.
    """
    ip = request.client.host if request.client else "unknown"
    await check_rate_limit(ip, x_provisioning_token)
    service = ProvisioningService(db)
    scope = await service.resolve_token(x_provisioning_token, ip)
    try:
        body = await request.json()
    except ValueError:
        raise UnprocessableError("request body must be JSON") from None
    if not isinstance(body, dict):
        raise UnprocessableError("request body must be a JSON object")
    device_uuid = body.get("device_uuid")
    if not isinstance(device_uuid, str):
        raise UnprocessableError("device_uuid is required")
    mac = body.get("mac_address")
    if not isinstance(mac, str):
        raise UnprocessableError("mac_address is required")
    result = await service.register_mac(scope, device_uuid, mac, ip)
    return EdgeRegisterResponse(
        api_key=result.api_key,
        device_uuid=result.device.device_uuid,
        site_id=result.site.code if result.site else "",
        site_profile=result.site_profile,
    )


@router.get("/config", response_model=EdgeConfig)
async def get_config(device: CurrentDevice, db: DBSession) -> EdgeConfig:
    return await EdgeService(db).build_config(device)


@router.get("/site-profile", response_model=EdgeSiteProfileResponse)
async def get_site_profile(device: CurrentDevice, db: DBSession) -> EdgeSiteProfileResponse:
    """Owner / site / contract data only, for the edge's "re-sync owner data" button."""
    _, profile = await device_site_profile(db, device.id)
    return EdgeSiteProfileResponse(site_profile=profile)


@router.post("/snapshots/presign", response_model=PresignResponse)
async def presign_snapshot(body: PresignRequest, device: CurrentDevice, db: DBSession) -> PresignResponse:
    return await EdgeService(db).presign_snapshot(device, body.camera_id, body.camera_code)


@router.put("/cameras", response_model=EdgeCameraSyncResult)
async def sync_cameras(body: EdgeCameraSync, device: CurrentDevice, db: DBSession) -> EdgeCameraSyncResult:
    """Send the edge's COMPLETE camera list (e.g. at startup and whenever it changes).

    Missing edge-managed cameras are disabled and flagged (not deleted) and come back when listed again.
    """
    return await EdgeService(db).sync_cameras(device, body)


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
