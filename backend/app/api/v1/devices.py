import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DBSession, OperatorUser, Pagination, ViewerUser
from app.core.enums import DeviceStatus, UserRole
from app.core.exceptions import PermissionDeniedError
from app.schemas.common import Page
from app.schemas.edge_device import (
    DeviceCommandRequest,
    EdgeConnectionInfo,
    EdgeDeviceCreate,
    EdgeDeviceRead,
    EdgeDeviceUpdate,
    EdgeDeviceWithKey,
)
from app.schemas.owner import DeviceAuditRead
from app.services.device_service import DeviceService
from app.services.owner_service import OwnerService

router = APIRouter()


@router.get("", response_model=Page[EdgeDeviceRead])
async def list_devices(
    db: DBSession,
    _: ViewerUser,
    pagination: Pagination,
    site_id: uuid.UUID | None = None,
    status: DeviceStatus | None = None,
) -> Page[EdgeDeviceRead]:
    return await DeviceService(db).list(pagination, site_id, status)


def _admin_fields(body, user) -> None:
    """MAC binding, owner and admin state decide who may provision / use a device: admins only."""
    sensitive = {"mac_address", "owner_id", "admin_state"} & body.model_dump(exclude_unset=True).keys()
    if sensitive and user.role != UserRole.ADMIN:
        raise PermissionDeniedError(f"only administrators may change {', '.join(sorted(sensitive))}")


@router.post("", response_model=EdgeDeviceWithKey, status_code=status.HTTP_201_CREATED)
async def create_device(body: EdgeDeviceCreate, db: DBSession, user: OperatorUser) -> EdgeDeviceWithKey:
    _admin_fields(body, user)
    """Pre-provision a device. The returned `api_key` is shown ONCE, with the connection info to hand over
    (the shared MQTT password only to admins)."""
    return await DeviceService(db).create(body, include_mqtt_password=user.role == UserRole.ADMIN)


@router.get("/{device_id}", response_model=EdgeDeviceRead)
async def get_device(device_id: uuid.UUID, db: DBSession, _: ViewerUser) -> EdgeDeviceRead:
    return await DeviceService(db).get_read(device_id)


@router.patch("/{device_id}", response_model=EdgeDeviceRead)
async def update_device(
    device_id: uuid.UUID, body: EdgeDeviceUpdate, db: DBSession, user: OperatorUser
) -> EdgeDeviceRead:
    _admin_fields(body, user)
    return await DeviceService(db).update(device_id, body)


@router.get("/{device_id}/audit", response_model=list[DeviceAuditRead])
async def device_audit(device_id: uuid.UUID, db: DBSession, _: AdminUser) -> list[DeviceAuditRead]:
    """Registrations, key rotations and rejected attempts (never contains a key or token)."""
    return await OwnerService(db).device_audit(device_id)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: uuid.UUID, db: DBSession, _: OperatorUser) -> None:
    await DeviceService(db).delete(device_id)


@router.post("/{device_id}/rotate-key", response_model=EdgeDeviceWithKey)
async def rotate_device_key(device_id: uuid.UUID, db: DBSession, _: AdminUser) -> EdgeDeviceWithKey:
    return await DeviceService(db).rotate_key(device_id)


@router.get("/{device_id}/connection", response_model=EdgeConnectionInfo)
async def get_device_connection(device_id: uuid.UUID, db: DBSession, _: AdminUser) -> EdgeConnectionInfo:
    """Connection info to hand over again later. The device key is never retrievable: rotate it if lost."""
    return await DeviceService(db).connection(device_id)


@router.post("/{device_id}/commands", status_code=status.HTTP_202_ACCEPTED)
async def send_device_command(
    device_id: uuid.UUID, body: DeviceCommandRequest, db: DBSession, _: OperatorUser
) -> dict:
    return await DeviceService(db).send_command(device_id, body.command, body.params)
