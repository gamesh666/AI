"""Reports built on the edge (authenticated with X-Device-Key).

The order arrives as a `generate_report` command in the heartbeat answer; the edge reports progress here
and uploads the PDF. `report-options` keeps the platform's report dialog in step with the edge's employees,
departments and seats.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import CurrentDevice, DBSession
from app.api.v1.edge_telemetry import _json, _object, _validate
from app.schemas.report import DeviceReportRead, ReportOptions, ReportStatusUpdate
from app.services.report_service import MAX_PDF_BYTES, PayloadTooLargeError, ReportService

router = APIRouter()


@router.put("/report-options", status_code=204)
async def put_report_options(request: Request, device: CurrentDevice, db: DBSession) -> None:
    data = _object(await _json(request, max_bytes=2 * 1024 * 1024))
    await ReportService(db).save_options(device, _validate(ReportOptions, data, "report options"))


@router.post("/reports/{report_id}/status", status_code=204)
async def report_status(report_id: uuid.UUID, request: Request, device: CurrentDevice, db: DBSession) -> None:
    data = _object(await _json(request))
    await ReportService(db).update_status(device, report_id, _validate(ReportStatusUpdate, data, "report status"))


@router.put("/reports/{report_id}/file", response_model=DeviceReportRead)
async def upload_report(
    report_id: uuid.UUID, request: Request, device: CurrentDevice, db: DBSession
) -> DeviceReportRead:
    """Body = the PDF itself (Content-Type: application/pdf)."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_PDF_BYTES:
        raise PayloadTooLargeError(f"report too large (max {MAX_PDF_BYTES} bytes)")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_PDF_BYTES:
            raise PayloadTooLargeError(f"report too large (max {MAX_PDF_BYTES} bytes)")
    return await ReportService(db).upload(device, report_id, bytes(data))
