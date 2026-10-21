from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ModelUsageCamera(BaseModel):
    code: str
    camera_id: uuid.UUID | None = None  # None = the edge reports a camera the platform does not know
    name: str | None = None


class ModelUsageDevice(BaseModel):
    device_id: uuid.UUID
    device_uuid: str
    device_name: str
    site_name: str | None = None
    status: str
    reported_at: datetime | None = None
    cameras: list[ModelUsageCamera]


class ModelUsage(BaseModel):
    """One model (name + version) and every edge / camera reporting it."""

    name: str
    version: str | None = None
    type: str | None = None
    task: str | None = None
    labels: list[str] = []
    devices: list[ModelUsageDevice]
    camera_count: int
    # other versions of the same model name run elsewhere -> worth aligning
    other_versions: list[str] = []


class SilentDevice(BaseModel):
    device_id: uuid.UUID
    device_uuid: str
    device_name: str
    status: str


class ModelUsageOverview(BaseModel):
    models: list[ModelUsage]
    # devices that never reported which models they run
    not_reporting: list[SilentDevice]
