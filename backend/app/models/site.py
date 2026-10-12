from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.edge_device import EdgeDevice
    from app.models.owner import Owner


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    # short slug used in stream paths, e.g. "site01" -> ai/site01/<device>/<camera>
    code: Mapped[str] = mapped_column(String(32), unique=True)
    address: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    # ---- owner / contract / licence (site_profile handed to edges) ----
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("owners.id", ondelete="SET NULL"), index=True)
    profile: Mapped[str | None] = mapped_column(String(16))  # office | construction | factory | security
    license_code: Mapped[str | None] = mapped_column(String(128))
    license_until: Mapped[date | None] = mapped_column(Date)
    contract_no: Mapped[str | None] = mapped_column(String(128))
    term_years: Mapped[int | None] = mapped_column(Integer)
    transaction_type: Mapped[str | None] = mapped_column(String(16))  # buyout | lease

    owner: Mapped[Owner | None] = relationship(back_populates="sites")
    edge_devices: Mapped[list[EdgeDevice]] = relationship(back_populates="site")
