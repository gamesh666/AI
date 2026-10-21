from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.site import Site


class Owner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """業主: the customer that owns sites and edge devices (company + contact data for site_profile)."""

    __tablename__ = "owners"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    company_name: Mapped[str | None] = mapped_column(String(128))
    company_address: Mapped[str | None] = mapped_column(String(256))
    company_phone: Mapped[str | None] = mapped_column(String(32))
    tax_id: Mapped[str | None] = mapped_column(String(8))
    contact_name: Mapped[str | None] = mapped_column(String(128))
    contact_phone: Mapped[str | None] = mapped_column(String(32))

    sites: Mapped[list[Site]] = relationship(back_populates="owner")


class ProvisioningToken(UUIDPrimaryKeyMixin, Base):
    """Factory provisioning token: lets edges register themselves into one owner (and optionally a site)."""

    __tablename__ = "provisioning_tokens"

    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16))  # first characters, to recognise it in the UI
    label: Mapped[str | None] = mapped_column(String(128))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"))
    # devices registered with this token get IDs <prefix>01, <prefix>02, ...
    device_prefix: Mapped[str] = mapped_column(String(16), default="REACH")
    max_devices: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[Owner] = relationship()
    site: Mapped[Site | None] = relationship()


class EdgeDeviceAudit(UUIDPrimaryKeyMixin, Base):
    """registered / re_registered / key_rotated / rejected_* — never contains a key or token."""

    __tablename__ = "edge_device_audit"

    edge_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="SET NULL"), index=True
    )
    device_uuid: Mapped[str | None] = mapped_column(String(64))
    mac_address: Mapped[str | None] = mapped_column(String(17))
    action: Mapped[str] = mapped_column(String(32), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    token_prefix: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
