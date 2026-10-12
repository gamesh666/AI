"""Edge self-registration (POST /edge/register).

Two flows:
- MAC flow (REACH AI BOX contract, docs/reach-edge-register/CLAUDE.md): the body carries `mac_address`;
  the device is identified by its MAC, belongs to the owner of the provisioning token, gets a platform ID
  (<prefix>01, <prefix>02, ...) and a fresh key on every (re-)registration.
- legacy flow (AIVMS edge-agent): no MAC, the platform-wide token from EDGE_PROVISIONING_TOKEN, the
  device ID chosen by the agent. It can never take over a device that has a MAC or an owner.

Nothing here ever logs a token, a key, a tax ID or a phone number.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.enums import DeviceStatus
from app.core.exceptions import AuthError, ConflictError, DomainError, PermissionDeniedError
from app.core.redis import get_redis
from app.core.security import constant_time_equals, generate_opaque_token, hash_token
from app.models.edge_device import EdgeDevice
from app.models.owner import EdgeDeviceAudit, ProvisioningToken
from app.models.site import Site
from app.schemas.edge_device import DEVICE_UUID_PATTERN
from app.services.site_profile import build_site_profile

logger = logging.getLogger(__name__)

MAC_DEVICE_PREFIX = "REACH-"
RATE_PER_MINUTE = 10
MAX_AUTH_FAILURES = 5
BLOCK_SECONDS = 15 * 60


class UnprocessableError(DomainError):
    status_code = 422


class TooManyRequestsError(DomainError):
    status_code = 429


# ---- MAC ----------------------------------------------------------------------------------------


def normalize_mac(raw: str) -> str:
    """'AA-BB-CC-DD-EE-FF' / 'aabb.ccdd.eeff' -> 'aa:bb:cc:dd:ee:ff'. Rejects zero, multicast, broadcast."""
    hexes = re.sub(r"[:\-.]", "", raw or "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", hexes):
        raise UnprocessableError("mac_address must be 12 hex digits, e.g. aa:bb:cc:dd:ee:ff")
    if hexes == "0" * 12:
        raise UnprocessableError("mac_address must not be all zeros")
    if int(hexes[:2], 16) & 1:  # multicast bit (also covers ff:ff:ff:ff:ff:ff broadcast)
        raise UnprocessableError("mac_address must be a unicast address")
    return ":".join(hexes[i:i + 2] for i in range(0, 12, 2))


def device_uuid_for_mac(mac: str) -> str:
    return MAC_DEVICE_PREFIX + mac.replace(":", "").upper()


# ---- rate limiting (Redis) ------------------------------------------------------------------------


async def check_rate_limit(ip: str, token: str | None) -> None:
    """10 requests / minute per IP + token; an IP with 5 consecutive 401s is blocked for 15 minutes."""
    try:
        redis = get_redis()
        if await redis.exists(f"aivms:reg:block:{ip}"):
            raise TooManyRequestsError("too many failed attempts from this address; try again later")
        key = f"aivms:reg:rate:{ip}:{hash_token(token or '')[:12]}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > RATE_PER_MINUTE:
            raise TooManyRequestsError("too many registration requests; try again in a minute")
    except TooManyRequestsError:
        raise
    except Exception:  # Redis unavailable: do not block registrations, but say so
        logger.warning("registration rate limiting unavailable (Redis error)")


async def record_auth_failure(ip: str) -> None:
    try:
        redis = get_redis()
        key = f"aivms:reg:fail:{ip}"
        failures = await redis.incr(key)
        await redis.expire(key, BLOCK_SECONDS)
        if failures >= MAX_AUTH_FAILURES:
            await redis.set(f"aivms:reg:block:{ip}", "1", ex=BLOCK_SECONDS)
            await redis.delete(key)
            logger.warning("registration: %s blocked for %ds after %d invalid tokens", ip, BLOCK_SECONDS, failures)
    except Exception:
        logger.warning("registration rate limiting unavailable (Redis error)")


async def reset_auth_failures(ip: str) -> None:
    try:
        await get_redis().delete(f"aivms:reg:fail:{ip}")
    except Exception:
        pass


# ---- registration ---------------------------------------------------------------------------------


@dataclass
class TokenScope:
    """Who a provisioning token registers devices for. token=None: the platform-wide legacy token."""

    token: ProvisioningToken | None
    prefix: str  # first characters, for the audit log

    @property
    def owner_id(self) -> uuid.UUID | None:
        return self.token.owner_id if self.token else None


@dataclass
class Registration:
    device: EdgeDevice
    api_key: str
    site: Site | None
    site_profile: dict[str, Any] | None


class ProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(self, action: str, ip: str, scope: TokenScope | None, device: EdgeDevice | None = None,
                     device_uuid: str | None = None, mac: str | None = None, **detail: Any) -> None:
        self.session.add(EdgeDeviceAudit(
            edge_device_id=device.id if device else None,
            device_uuid=device.device_uuid if device else device_uuid,
            mac_address=device.mac_address if device and device.mac_address else mac,
            action=action, source_ip=ip, token_prefix=scope.prefix if scope else None, detail=detail,
        ))

    async def resolve_token(self, token: str | None, ip: str) -> TokenScope:
        if not token:
            await record_auth_failure(ip)
            await self._audit("rejected_401", ip, None, reason="missing token")
            await self.session.commit()
            raise AuthError("missing X-Provisioning-Token")
        now = datetime.now(UTC)
        token_hash = hash_token(token)
        row = (
            await self.session.execute(select(ProvisioningToken).where(ProvisioningToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if row is not None and constant_time_equals(row.token_hash, token_hash):
            if row.revoked_at is None and (row.expires_at is None or row.expires_at > now):
                await reset_auth_failures(ip)
                return TokenScope(token=row, prefix=row.token_prefix)
        elif constant_time_equals(token, get_settings().edge_provisioning_token.get_secret_value()):
            await reset_auth_failures(ip)
            return TokenScope(token=None, prefix="platform")
        await record_auth_failure(ip)
        await self._audit("rejected_401", ip, None, reason="invalid, revoked or expired token")
        await self.session.commit()
        raise AuthError("invalid, revoked or expired provisioning token")

    async def register_mac(self, scope: TokenScope, device_uuid: str, raw_mac: str, ip: str) -> Registration:
        mac = normalize_mac(raw_mac)
        if device_uuid != device_uuid_for_mac(mac):
            raise UnprocessableError("device_uuid must be REACH- followed by the MAC in upper-case hex")

        device = (
            await self.session.execute(select(EdgeDevice).where(EdgeDevice.mac_address == mac))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        api_key = generate_opaque_token()

        if device is None:
            await self._check_quota(scope)
            device = await self._create(scope, mac, api_key, now)
            await self._audit("registered", ip, scope, device)
            logger.info("registered %s (mac %s, token %s)", device.device_uuid, mac, scope.prefix)
        else:
            if device.owner_id is not None and device.owner_id != scope.owner_id:
                await self._audit("rejected_409", ip, scope, device_uuid=device_uuid, mac=mac)
                await self.session.commit()
                logger.warning("registration of mac %s refused: registered under another owner", mac)
                raise ConflictError("this MAC address is already registered to another device")
            if device.admin_state != "active":
                await self._audit("rejected_403", ip, scope, device, reason=device.admin_state)
                await self.session.commit()
                raise PermissionDeniedError(f"this device is {device.admin_state} on the platform")
            if device.owner_id is None and scope.token is not None:
                # a device the admin pre-created (MAC filled in) is claimed by its owner's token
                device.owner_id = scope.token.owner_id
            if device.site_id is None and scope.token is not None and scope.token.site_id is not None:
                device.site_id = scope.token.site_id
            if scope.token is not None:
                device.provisioning_token_id = scope.token.id
            device.api_key_hash = hash_token(api_key)
            device.registered_at = device.registered_at or now
            device.last_registered_at = now
            await self._audit("re_registered", ip, scope, device, key_rotated=True)
            logger.info("re-registered %s (mac %s); key rotated", device.device_uuid, mac)
        await self.session.commit()
        return await self._result(device.id, api_key)

    async def _check_quota(self, scope: TokenScope) -> None:
        token = scope.token
        if token is None or token.max_devices is None:
            return
        used = (
            await self.session.execute(
                select(func.count()).select_from(EdgeDevice).where(EdgeDevice.provisioning_token_id == token.id)
            )
        ).scalar_one()
        if used >= token.max_devices:
            raise PermissionDeniedError(
                f"device quota of this provisioning token reached ({token.max_devices}); ask the platform admin"
            )

    async def _create(self, scope: TokenScope, mac: str, api_key: str, now: datetime) -> EdgeDevice:
        token = scope.token
        # plain values: a rollback below expires ORM objects
        prefix = token.device_prefix if token else None
        owner_id, site_id, token_id = (token.owner_id, token.site_id, token.id) if token else (None, None, None)
        for _ in range(5):
            device_uuid = await self._next_device_uuid(prefix) if prefix else device_uuid_for_mac(mac)
            device = EdgeDevice(
                device_uuid=device_uuid, name=device_uuid, mac_address=mac, api_key_hash=hash_token(api_key),
                status=DeviceStatus.PENDING, admin_state="active", owner_id=owner_id, site_id=site_id,
                provisioning_token_id=token_id, registered_at=now, last_registered_at=now,
            )
            self.session.add(device)
            try:
                await self.session.flush()
                return device
            except IntegrityError:  # someone took that ID in the meantime: next number
                await self.session.rollback()
        raise ConflictError("could not allocate a device ID; please retry")

    async def _next_device_uuid(self, prefix: str) -> str:
        rows = (
            await self.session.execute(select(EdgeDevice.device_uuid).where(EdgeDevice.device_uuid.like(f"{prefix}%")))
        ).scalars().all()
        numbers = [int(m.group(1)) for d in rows if (m := re.fullmatch(rf"{re.escape(prefix)}(\d+)", d))]
        return f"{prefix}{(max(numbers, default=0) + 1):02d}"

    async def _result(self, device_id: uuid.UUID, api_key: str) -> Registration:
        device = await load_device_with_profile(self.session, device_id)
        site = device.site
        owner = device.owner or (site.owner if site else None)
        return Registration(device=device, api_key=api_key, site=site,
                            site_profile=build_site_profile(device, site, owner))

    async def register_legacy(self, scope: TokenScope, device_uuid: str, info: dict[str, Any],
                              ip: str) -> Registration:
        """AIVMS edge-agent: platform-wide token, agent-chosen ID. Never takes over a provisioned box."""
        if scope.token is not None:
            raise UnprocessableError("mac_address is required with an owner provisioning token")
        if not re.fullmatch(DEVICE_UUID_PATTERN, device_uuid or ""):
            raise UnprocessableError("device_uuid must be 3-64 characters of A-Z a-z 0-9 _ -")
        device = (
            await self.session.execute(select(EdgeDevice).where(EdgeDevice.device_uuid == device_uuid))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        api_key = generate_opaque_token()
        if device is None:
            device = EdgeDevice(device_uuid=device_uuid, name=info.get("name") or device_uuid,
                                status=DeviceStatus.PENDING, registered_at=now)
            self.session.add(device)
            action = "registered"
        else:
            if device.mac_address or device.owner_id:
                await self._audit("rejected_409", ip, scope, device)
                await self.session.commit()
                raise ConflictError("this device ID is provisioned per owner; use its owner provisioning token")
            if device.admin_state != "active":
                await self._audit("rejected_403", ip, scope, device, reason=device.admin_state)
                await self.session.commit()
                raise PermissionDeniedError(f"this device is {device.admin_state} on the platform")
            action = "re_registered"
        for field in ("hostname", "ip_address", "agent_version", "gpu_name", "gpu_memory"):
            if info.get(field) is not None:
                setattr(device, field, info[field])
        device.api_key_hash = hash_token(api_key)
        device.last_registered_at = now
        await self.session.flush()
        await self._audit(action, ip, scope, device, key_rotated=action == "re_registered")
        await self.session.commit()
        return await self._result(device.id, api_key)


async def load_device_with_profile(session: AsyncSession, device_id: uuid.UUID) -> EdgeDevice:
    stmt = (
        select(EdgeDevice)
        .where(EdgeDevice.id == device_id)
        .options(selectinload(EdgeDevice.site).selectinload(Site.owner), selectinload(EdgeDevice.owner))
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one()


async def device_site_profile(session: AsyncSession, device_id: uuid.UUID) -> tuple[str, dict[str, Any] | None]:
    """(site_id for the edge = site code or "", site_profile) of a device."""
    device = await load_device_with_profile(session, device_id)
    site = device.site
    owner = device.owner or (site.owner if site else None)
    return (site.code if site else ""), build_site_profile(device, site, owner)
