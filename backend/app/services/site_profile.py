"""site_profile handed to edges (REACH AI BOX register contract §3.6).

Keys and rules are fixed by the contract: the BOX drops the WHOLE profile if one field is invalid, so the
platform validates with the very same rules, both when the data is edited and when it is sent.
Missing data is omitted (never ""), so the BOX keeps its local value.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.models.edge_device import EdgeDevice
from app.models.owner import Owner
from app.models.site import Site

PROFILES = ("office", "construction", "factory", "security")
TRANSACTION_TYPES = ("buyout", "lease")
PHONE_PATTERN = r"^[0-9+()#\- ]{0,32}$"
TAX_ID_PATTERN = r"^(\d{8})?$"

Phone = Annotated[str, Field(pattern=PHONE_PATTERN)]
Text128 = Annotated[str, Field(max_length=128)]


class SiteProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_name: Text128 | None = None
    profile: Literal["office", "construction", "factory", "security"] | None = None
    site_code: Text128 | None = None
    host_code: Text128 | None = None
    license_code: Text128 | None = None
    license_until: str | None = None  # YYYY-MM-DD or ""
    contract_no: Text128 | None = None
    term_years: Annotated[StrictInt, Field(ge=0, le=99)] | None = None
    transaction_type: Literal["", "buyout", "lease"] | None = None
    company_name: Text128 | None = None
    company_address: Annotated[str, Field(max_length=256)] | None = None
    company_phone: Phone | None = None
    tax_id: Annotated[str, Field(pattern=TAX_ID_PATTERN)] | None = None
    contact_name: Text128 | None = None
    contact_phone: Phone | None = None

    @field_validator("license_until")
    @classmethod
    def _date(cls, v: str | None) -> str | None:
        if v:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError("license_until must be YYYY-MM-DD")
            date.fromisoformat(v)
        return v

    def payload(self) -> dict[str, Any] | None:
        data = self.model_dump(exclude_none=True)
        return data or None


def build_site_profile(device: EdgeDevice, site: Site | None, owner: Owner | None) -> dict[str, Any] | None:
    """Owner + site (+ contract / licence) of a device; None when the platform knows nothing yet."""
    if site is None and owner is None:
        return None
    values: dict[str, Any] = {"host_code": device.device_uuid}
    if site is not None:
        values.update(
            site_name=site.name,
            site_code=site.code,
            profile=site.profile,
            license_code=site.license_code,
            license_until=site.license_until.isoformat() if site.license_until else None,
            contract_no=site.contract_no,
            term_years=site.term_years,
            transaction_type=site.transaction_type,
        )
    if owner is not None:
        values.update(
            company_name=owner.company_name,
            company_address=owner.company_address,
            company_phone=owner.company_phone,
            tax_id=owner.tax_id,
            contact_name=owner.contact_name,
            contact_phone=owner.contact_phone,
        )
        values.setdefault("site_name", owner.name)
    return SiteProfile.model_validate({k: v for k, v in values.items() if v is not None}).payload()
