"""業主 (owners) and their provisioning tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_opaque_token, hash_token
from app.models.edge_device import EdgeDevice
from app.models.owner import EdgeDeviceAudit, Owner, ProvisioningToken
from app.models.site import Site
from app.schemas.owner import (
    DeviceAuditRead,
    OwnerCreate,
    OwnerRead,
    OwnerUpdate,
    ProvisioningTokenCreate,
    ProvisioningTokenCreated,
    ProvisioningTokenRead,
)

TOKEN_PREFIX = "aivms_pt_"  # recognisable in configs; the random part follows


# a revoked token stays visible this long (to see what was revoked), then it is deleted
REVOKED_TOKEN_TTL = timedelta(minutes=5)


class OwnerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _counts(self, model, column, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        stmt = select(column, func.count()).select_from(model).where(column.in_(ids)).group_by(column)
        return dict((await self.session.execute(stmt)).all())

    async def list(self) -> list[OwnerRead]:
        owners = list((await self.session.execute(select(Owner).order_by(Owner.name))).scalars().all())
        ids = [o.id for o in owners]
        sites = await self._counts(Site, Site.owner_id, ids)
        devices = await self._counts(EdgeDevice, EdgeDevice.owner_id, ids)
        tokens = await self._counts(ProvisioningToken, ProvisioningToken.owner_id, ids)
        result = []
        for o in owners:
            dto = OwnerRead.model_validate(o)
            dto.site_count, dto.device_count, dto.token_count = sites.get(o.id, 0), devices.get(o.id, 0), tokens.get(
                o.id, 0)
            result.append(dto)
        return result

    async def get(self, owner_id: uuid.UUID) -> Owner:
        owner = await self.session.get(Owner, owner_id)
        if owner is None:
            raise NotFoundError("owner not found")
        return owner

    async def create(self, data: OwnerCreate) -> OwnerRead:
        owner = Owner(**data.model_dump())
        self.session.add(owner)
        await self._commit()
        return OwnerRead.model_validate(owner)

    async def update(self, owner_id: uuid.UUID, data: OwnerUpdate) -> OwnerRead:
        owner = await self.get(owner_id)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(owner, k, v)
        await self._commit()
        return OwnerRead.model_validate(owner)

    async def delete(self, owner_id: uuid.UUID) -> None:
        await self.session.delete(await self.get(owner_id))
        await self.session.commit()

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("an owner with this name already exists") from exc

    # ---- provisioning tokens ------------------------------------------------------------------

    async def _token_read(self, token: ProvisioningToken, used: int) -> ProvisioningTokenRead:
        now = datetime.now(UTC)
        state = "revoked" if token.revoked_at else ("expired" if token.expires_at and token.expires_at <= now
                                                    else "active")
        return ProvisioningTokenRead(
            id=token.id, token_prefix=token.token_prefix, label=token.label, owner_id=token.owner_id,
            site_id=token.site_id, site_name=token.site.name if token.site else None,
            device_prefix=token.device_prefix, max_devices=token.max_devices, used_devices=used,
            expires_at=token.expires_at, revoked_at=token.revoked_at, created_at=token.created_at, state=state,
        )

    async def purge_revoked(self, owner_id: uuid.UUID | None = None,
                            older_than: timedelta = REVOKED_TOKEN_TTL) -> int:
        """Delete tokens revoked longer ago than `older_than` (devices keep working: they hold their own key)."""
        stmt = delete(ProvisioningToken).where(
            ProvisioningToken.revoked_at.is_not(None),
            ProvisioningToken.revoked_at <= datetime.now(UTC) - older_than,
        )
        if owner_id is not None:
            stmt = stmt.where(ProvisioningToken.owner_id == owner_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def tokens(self, owner_id: uuid.UUID) -> list[ProvisioningTokenRead]:
        await self.get(owner_id)
        await self.purge_revoked(owner_id)
        stmt = (
            select(ProvisioningToken).where(ProvisioningToken.owner_id == owner_id)
            .options(selectinload(ProvisioningToken.site)).order_by(ProvisioningToken.created_at.desc())
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        used = await self._counts(EdgeDevice, EdgeDevice.provisioning_token_id, [t.id for t in rows])
        return [await self._token_read(t, used.get(t.id, 0)) for t in rows]

    async def create_token(self, owner_id: uuid.UUID, data: ProvisioningTokenCreate,
                           created_by: uuid.UUID | None) -> ProvisioningTokenCreated:
        await self.get(owner_id)
        if data.site_id is not None:
            site = await self.session.get(Site, data.site_id)
            if site is None:
                raise NotFoundError("site not found")
        secret = TOKEN_PREFIX + generate_opaque_token(32)
        token = ProvisioningToken(
            token_hash=hash_token(secret), token_prefix=secret[: len(TOKEN_PREFIX) + 4], owner_id=owner_id,
            created_by=created_by, **data.model_dump(),
        )
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token, ["site", "created_at"])
        read = await self._token_read(token, 0)
        return ProvisioningTokenCreated(**read.model_dump(), token=secret)

    async def revoke_token(self, token_id: uuid.UUID) -> ProvisioningTokenRead:
        token = await self.session.get(ProvisioningToken, token_id)
        if token is None:
            raise NotFoundError("provisioning token not found")
        if token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)
            await self.session.commit()
        await self.session.refresh(token, ["site"])
        used = await self._counts(EdgeDevice, EdgeDevice.provisioning_token_id, [token.id])
        return await self._token_read(token, used.get(token.id, 0))

    # ---- audit ---------------------------------------------------------------------------------

    async def device_audit(self, device_id: uuid.UUID, limit: int = 200) -> list[DeviceAuditRead]:
        stmt = (
            select(EdgeDeviceAudit).where(EdgeDeviceAudit.edge_device_id == device_id)
            .order_by(EdgeDeviceAudit.created_at.desc()).limit(limit)
        )
        return [DeviceAuditRead.model_validate(a) for a in (await self.session.execute(stmt)).scalars().all()]
