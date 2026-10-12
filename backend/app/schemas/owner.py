from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.site_profile import PHONE_PATTERN

DEVICE_PREFIX_PATTERN = r"^[A-Za-z][A-Za-z0-9_\-]{0,15}$"


def _blank_to_none(v: Any) -> Any:
    return None if isinstance(v, str) and v.strip() == "" else v


class _OwnerFields(BaseModel):
    company_name: str | None = Field(default=None, max_length=128)
    company_address: str | None = Field(default=None, max_length=256)
    company_phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    tax_id: str | None = Field(default=None, pattern=r"^\d{8}$")
    contact_name: str | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, pattern=PHONE_PATTERN)

    _blank = field_validator(
        "company_name", "company_address", "company_phone", "tax_id", "contact_name", "contact_phone", mode="before"
    )(_blank_to_none)


class OwnerCreate(_OwnerFields):
    name: str = Field(min_length=1, max_length=128)


class OwnerUpdate(_OwnerFields):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class OwnerRead(ORMModel):
    id: uuid.UUID
    name: str
    company_name: str | None
    company_address: str | None
    company_phone: str | None
    tax_id: str | None
    contact_name: str | None
    contact_phone: str | None
    created_at: datetime
    site_count: int = 0
    device_count: int = 0
    token_count: int = 0


class ProvisioningTokenCreate(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    site_id: uuid.UUID | None = None
    device_prefix: str = Field(default="REACH", pattern=DEVICE_PREFIX_PATTERN)
    max_devices: int | None = Field(default=None, ge=1, le=100000)
    expires_at: datetime | None = None


class ProvisioningTokenRead(BaseModel):
    id: uuid.UUID
    token_prefix: str
    label: str | None
    owner_id: uuid.UUID
    site_id: uuid.UUID | None
    site_name: str | None = None
    device_prefix: str
    max_devices: int | None
    used_devices: int = 0
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    state: Literal["active", "revoked", "expired"]


class ProvisioningTokenCreated(ProvisioningTokenRead):
    """Returned once, at creation: the token itself is never retrievable again (only its hash is stored)."""

    token: str


class DeviceAuditRead(ORMModel):
    id: uuid.UUID
    action: str
    device_uuid: str | None
    mac_address: str | None
    source_ip: str | None
    token_prefix: str | None
    detail: dict[str, Any]
    created_at: datetime
