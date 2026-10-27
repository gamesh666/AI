import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DBSession, OperatorUser, Pagination, ViewerUser
from app.core.enums import DeviceStatus, UserRole
from app.core.exceptions import PermissionDeniedError
from app.schemas.common import Page
from app.schemas.edge_device import DeviceCommandRequest, EdgeDeviceRead, EdgeDeviceUpdate
from app.schemas.owner import DeviceAuditRead
from app.schemas.report import DeviceReportRead, ReportDownload, ReportFilters, ReportOptionsRead
from app.services.device_service import DeviceService
from app.services.owner_service import OwnerService
from app.services.report_service import ReportService

router = APIRouter()
reports_router = APIRouter()


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
    """Registrations and rejected attempts (never contains a key or token)."""
    return await OwnerService(db).device_audit(device_id)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: uuid.UUID, db: DBSession, _: OperatorUser) -> None:
    await DeviceService(db).delete(device_id)


@router.post("/{device_id}/commands", status_code=status.HTTP_202_ACCEPTED)
async def send_device_command(
    device_id: uuid.UUID, body: DeviceCommandRequest, db: DBSession, _: OperatorUser
) -> dict:
    return await DeviceService(db).send_command(device_id, body.command, body.params)


# ---- 出勤事件報表 (built on the edge from its own database) -------------------------------------


@router.get("/{device_id}/report-options", response_model=ReportOptionsRead)
async def report_options(device_id: uuid.UUID, db: DBSession, _: AdminUser) -> ReportOptionsRead:
    """Employees, departments, seats... as last sent by the edge."""
    return await ReportService(db).options(await DeviceService(db).get(device_id))


@router.get("/{device_id}/reports", response_model=list[DeviceReportRead])
async def list_reports(device_id: uuid.UUID, db: DBSession, _: AdminUser) -> list[DeviceReportRead]:
    return await ReportService(db).list(await DeviceService(db).get(device_id))


@router.post("/{device_id}/reports", response_model=DeviceReportRead, status_code=status.HTTP_202_ACCEPTED)
async def request_report(
    device_id: uuid.UUID, body: ReportFilters, db: DBSession, user: AdminUser
) -> DeviceReportRead:
    """Sent to the edge with its next heartbeat; the edge uploads the PDF when done."""
    return await ReportService(db).request(await DeviceService(db).get(device_id), body, user.id)


@reports_router.get("/{report_id}/download", response_model=ReportDownload)
async def download_report(report_id: uuid.UUID, db: DBSession, _: AdminUser) -> ReportDownload:
    return await ReportService(db).download(report_id)
