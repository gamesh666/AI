"""出勤事件報表 generated on the edge: the request filters, the edge's choices and the report rows."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

MAX_REPORT_DAYS = 366

Period = Literal["yesterday", "last_week", "last_month", "last_year", "custom"]
AttendanceStatus = Literal[
    "on_time", "late_pending_review", "late_confirmed", "late_rejected", "identity_conflict", "not_arrived",
    "normal_departure", "early_leave_pending_review", "early_leave_confirmed", "early_leave_rejected",
    "not_judged", "unverifiable",
]
VlmResult = Literal["supported", "not_supported", "undetermined", "model_unavailable", "disabled"]
ReviewState = Literal["pending", "confirmed", "rejected", "not_required"]
FaceResult = Literal["matched", "unverified"]

_Code = Field(default=None, max_length=64)


class ReportFilters(BaseModel):
    """Same filters as the edge's own report screen; empty = all. Dates are the edge's local dates."""

    employee_id: str | None = _Code
    department: str | None = _Code
    seat: str | None = _Code
    period: Period = "custom"
    start_date: date
    end_date: date
    event: str | None = _Code
    status: str | None = _Code
    attendance_status: AttendanceStatus | None = None
    vlm: VlmResult | None = None
    review: ReviewState | None = None
    face: FaceResult | None = None

    @model_validator(mode="after")
    def _range(self) -> ReportFilters:
        if self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        if (self.end_date - self.start_date).days + 1 > MAX_REPORT_DAYS:
            raise ValueError(f"the period is longer than {MAX_REPORT_DAYS} days")
        return self


class ReportOption(BaseModel):
    value: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)


class ReportEmployee(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    department: str | None = Field(default=None, max_length=64)
    seat: str | None = Field(default=None, max_length=64)


class ReportOptions(BaseModel):
    """Choices for the report dialog, sent by the edge (PUT /edge/report-options) whenever they change."""

    employees: list[ReportEmployee] = Field(default_factory=list, max_length=5000)
    departments: list[ReportOption] = Field(default_factory=list, max_length=500)
    seats: list[ReportOption] = Field(default_factory=list, max_length=2000)
    events: list[ReportOption] = Field(default_factory=list, max_length=50)
    statuses: list[ReportOption] = Field(default_factory=list, max_length=50)


class ReportOptionsRead(ReportOptions):
    updated_at: datetime | None = None


class ReportStatusUpdate(BaseModel):
    """Edge -> platform while working on a report; `ready` is reached by uploading the PDF."""

    state: Literal["generating", "failed"]
    message: str | None = Field(default=None, max_length=512)


class DeviceReportRead(ORMModel):
    id: uuid.UUID
    edge_device_id: uuid.UUID
    kind: str
    filters: dict
    # queued | generating | ready | failed | expired (not finished in time)
    status: str
    message: str | None
    filename: str
    size_bytes: int | None
    created_at: datetime
    finished_at: datetime | None


class ReportDownload(BaseModel):
    url: str
    filename: str
