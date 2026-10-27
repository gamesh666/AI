"""出勤事件報表: the platform orders it, the edge builds the PDF from its own database and uploads it.

The platform never connects into an edge: the order travels in the heartbeat answer (`generate_report`),
the edge reports progress and uploads the file with its device key.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared.payloads import Command, CommandType
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models.edge_device import EdgeDevice
from app.models.report import DeviceReport
from app.schemas.report import (
    DeviceReportRead,
    ReportDownload,
    ReportFilters,
    ReportOptions,
    ReportOptionsRead,
    ReportStatusUpdate,
)
from app.services import storage_service, telemetry
from app.services.provisioning import UnprocessableError

# an order the edge has not finished by then is shown as expired (it may still upload later)
REPORT_TIMEOUT = timedelta(minutes=15)
KEEP_PER_DEVICE = 20
MAX_PDF_BYTES = 20 * 1024 * 1024
UPLOAD_PATH = "/edge/reports/{report_id}/file"
STATUS_PATH = "/edge/reports/{report_id}/status"


class PayloadTooLargeError(DomainError):
    status_code = 413


def _filename(f: ReportFilters) -> str:
    # same pattern as the edge's own export: attendance_<employee|all>_<start>_<end>.pdf
    who = "".join(c for c in (f.employee_id or "all") if c.isalnum() or c in "-_") or "all"
    return f"attendance_{who}_{f.start_date.isoformat()}_{f.end_date.isoformat()}.pdf"


def _read(report: DeviceReport) -> DeviceReportRead:
    read = DeviceReportRead.model_validate(report)
    if report.status in ("queued", "generating") and report.created_at < datetime.now(UTC) - REPORT_TIMEOUT:
        read.status = "expired"
    return read


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- admin --------------------------------------------------------------------------------

    async def options(self, device: EdgeDevice) -> ReportOptionsRead:
        return ReportOptionsRead(**(device.report_options or {}), updated_at=device.report_options_at)

    async def request(self, device: EdgeDevice, filters: ReportFilters, user_id: uuid.UUID | None) -> DeviceReportRead:
        report = DeviceReport(
            edge_device_id=device.id, kind="attendance", filters=filters.model_dump(mode="json"),
            status="queued", filename=_filename(filters), requested_by=user_id,
        )
        self.session.add(report)
        await self.session.flush()
        await telemetry.queue_command(device.device_uuid, Command(
            command=CommandType.GENERATE_REPORT,
            params={
                "report_id": str(report.id),
                "kind": "attendance",
                "format": "pdf",
                "filters": report.filters,
                "upload": {"method": "PUT", "path": UPLOAD_PATH.format(report_id=report.id),
                           "content_type": "application/pdf", "max_bytes": MAX_PDF_BYTES},
                "status": {"method": "POST", "path": STATUS_PATH.format(report_id=report.id)},
            },
        ))
        await self.session.commit()
        await self.session.refresh(report)
        await self._prune(device)
        return _read(report)

    async def list(self, device: EdgeDevice) -> list[DeviceReportRead]:
        rows = (await self.session.scalars(
            select(DeviceReport).where(DeviceReport.edge_device_id == device.id)
            .order_by(DeviceReport.created_at.desc()).limit(KEEP_PER_DEVICE)
        )).all()
        return [_read(r) for r in rows]

    async def download(self, report_id: uuid.UUID) -> ReportDownload:
        report = await self.session.get(DeviceReport, report_id)
        if report is None:
            raise NotFoundError("report not found")
        if report.status != "ready" or not report.object_key:
            raise ConflictError("the report is not ready yet")
        return ReportDownload(url=storage_service.presign_attachment(report.object_key, report.filename),
                              filename=report.filename)

    async def _prune(self, device: EdgeDevice) -> None:
        old = (await self.session.scalars(
            select(DeviceReport).where(DeviceReport.edge_device_id == device.id)
            .order_by(DeviceReport.created_at.desc()).offset(KEEP_PER_DEVICE)
        )).all()
        for r in old:
            if r.object_key:
                await storage_service.remove_object(r.object_key)
            await self.session.delete(r)
        if old:
            await self.session.commit()

    # ---- edge ---------------------------------------------------------------------------------

    async def save_options(self, device: EdgeDevice, options: ReportOptions) -> None:
        device.report_options = options.model_dump(mode="json")
        device.report_options_at = datetime.now(UTC)
        await self.session.commit()

    async def _own(self, device: EdgeDevice, report_id: uuid.UUID) -> DeviceReport:
        report = await self.session.get(DeviceReport, report_id)
        # another device's report looks exactly like a missing one
        if report is None or report.edge_device_id != device.id:
            raise NotFoundError("report not found")
        return report

    async def update_status(self, device: EdgeDevice, report_id: uuid.UUID, update: ReportStatusUpdate) -> None:
        report = await self._own(device, report_id)
        if report.status == "ready":
            raise ConflictError("the report has already been uploaded")
        report.status = update.state
        report.message = update.message
        if update.state == "failed":
            report.finished_at = datetime.now(UTC)
        await self.session.commit()

    async def upload(self, device: EdgeDevice, report_id: uuid.UUID, data: bytes) -> DeviceReportRead:
        report = await self._own(device, report_id)
        if len(data) > MAX_PDF_BYTES:
            raise PayloadTooLargeError(f"report too large (max {MAX_PDF_BYTES} bytes)")
        if not data.startswith(b"%PDF-"):
            raise UnprocessableError("the body must be the PDF file (application/pdf)")
        key = storage_service.report_key(device.device_uuid, report.id)
        await storage_service.put_bytes(key, data, "application/pdf")
        report.object_key = key
        report.size_bytes = len(data)
        report.status = "ready"
        report.message = None
        report.finished_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(report)
        return _read(report)
