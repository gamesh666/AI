from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

# site / camera IDs used in stream paths, e.g. site01, CAM001
SLUG_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_\-]{1,31}$"


def _blank_to_none(v: Any) -> Any:
    return None if isinstance(v, str) and v.strip() == "" else v


class _ContractFields(BaseModel):
    """Owner, profile, contract and licence (sent to edges as site_profile; same rules as the contract §3.6)."""

    owner_id: uuid.UUID | None = None
    profile: Literal["office", "construction", "factory", "security"] | None = None
    license_code: str | None = Field(default=None, max_length=128)
    license_until: date | None = None
    contract_no: str | None = Field(default=None, max_length=128)
    term_years: int | None = Field(default=None, ge=0, le=99, strict=True)
    transaction_type: Literal["buyout", "lease"] | None = None

    _blank = field_validator(
        "profile", "license_code", "license_until", "contract_no", "transaction_type", mode="before"
    )(_blank_to_none)


class SiteCreate(_ContractFields):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(pattern=SLUG_PATTERN, description="Slug used in stream paths, e.g. site01")
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteUpdate(_ContractFields):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    code: str | None = Field(default=None, pattern=SLUG_PATTERN)
    address: str | None = Field(default=None, max_length=255)
    description: str | None = None


class SiteRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    description: str | None
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    profile: str | None = None
    license_code: str | None = None
    license_until: date | None = None
    contract_no: str | None = None
    term_years: int | None = None
    transaction_type: str | None = None
    created_at: datetime
    device_count: int = 0
