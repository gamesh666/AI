from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared.payloads import CommandType, DeviceState, Heartbeat
from aivms_shared.payloads import DeviceStatus as DeviceStatusPayload
from app.core.config import get_settings
from app.core.enums import CameraStatus, DeviceStatus
from app.core.exceptions import AuthError, ConflictError, DomainError, NotFoundError
from app.core.redis import get_redis
from app.core.security import constant_time_equals, generate_opaque_token, hash_token
from app.messaging import publisher
from app.models.edge_device import EdgeDevice
from app.realtime.broadcaster import broadcaster
from app.realtime.messages import RealtimeEventType
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.common import Page, PageParams
from app.schemas.edge import EdgeRegisterRequest
from app.schemas.edge_device import (
    EdgeDeviceCreate,
    EdgeDeviceRead,
    EdgeDeviceUpdate,
    EdgeDeviceWithKey,
)
from app.services.mappers import device_to_read

HEARTBEAT_CACHE_KEY = "aivms:device:{uuid}:heartbeat"


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DeviceRepository(session)
        self.cameras = CameraRepository(session)

    # ---- admin CRUD -----------------------------------------------------------

    async def list(
        self, params: PageParams, site_id: uuid.UUID | None = None, status: DeviceStatus | None = None
    ) -> Page[EdgeDeviceRead]:
        rows, total = await self.repo.paginate(
            self.repo.list_stmt(site_id, status), params.offset, params.page_size
        )
        counts = await self.repo.camera_counts([d.id for d in rows])
        return Page(
            items=[device_to_read(d, counts.get(d.id, 0)) for d in rows],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def get(self, device_id: uuid.UUID) -> EdgeDevice:
        device = await self.repo.get(device_id)
        if not device:
            raise NotFoundError("edge device not found")
        await self.session.refresh(device, ["site"])
        return device

    async def get_read(self, device_id: uuid.UUID) -> EdgeDeviceRead:
        device = await self.get(device_id)
        counts = await self.repo.camera_counts([device.id])
        return device_to_read(device, counts.get(device.id, 0))

    async def create(self, data: EdgeDeviceCreate) -> EdgeDeviceWithKey:
        api_key = generate_opaque_token()
        device = EdgeDevice(**data.model_dump(), api_key_hash=hash_token(api_key), status=DeviceStatus.PENDING)
        try:
            await self.repo.add(device)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("device_uuid already exists") from exc
        await self.session.refresh(device, ["site"])
        return EdgeDeviceWithKey(**device_to_read(device).model_dump(), api_key=api_key)

    async def update(self, device_id: uuid.UUID, data: EdgeDeviceUpdate) -> EdgeDeviceRead:
        device = self.repo.apply_updates(await self.get(device_id), data.model_dump(exclude_unset=True))
        await self.session.commit()
        return await self.get_read(device.id)

    async def delete(self, device_id: uuid.UUID) -> None:
        await self.repo.delete(await self.get(device_id))
        await self.session.commit()

    async def rotate_key(self, device_id: uuid.UUID) -> EdgeDeviceWithKey:
        device = await self.get(device_id)
        api_key = generate_opaque_token()
        device.api_key_hash = hash_token(api_key)
        await self.session.commit()
        read = await self.get_read(device_id)
        return EdgeDeviceWithKey(**read.model_dump(), api_key=api_key)

    async def send_command(self, device_id: uuid.UUID, command: str, params: dict) -> dict:
        device = await self.get(device_id)
        try:
            cmd_type = CommandType(command)
        except ValueError as exc:
            raise DomainError(f"unknown command '{command}'") from exc
        sent = await publisher.send_command(device.device_uuid, cmd_type, params)
        return {"command_id": str(sent.command_id), "command": sent.command.value}

    # ---- edge-facing ----------------------------------------------------------

    async def authenticate(self, api_key: str) -> EdgeDevice:
        device = await self.repo.get_by_api_key_hash(hash_token(api_key))
        if not device:
            raise AuthError("invalid device key")
        return device

    async def register(self, data: EdgeRegisterRequest, provisioning_token: str) -> tuple[EdgeDevice, str]:
        """Self-registration with the shared provisioning token. Re-registering rotates the key."""
        expected = get_settings().edge_provisioning_token.get_secret_value()
        if not constant_time_equals(provisioning_token, expected):
            raise AuthError("invalid provisioning token")
        api_key = generate_opaque_token()
        device = await self.repo.get_by_device_uuid(data.device_uuid)
        if device is None:
            device = EdgeDevice(device_uuid=data.device_uuid, name=data.name or data.device_uuid)
            self.session.add(device)
        info = data.model_dump(exclude={"device_uuid", "name"}, exclude_none=True)
        self.repo.apply_updates(device, info)
        device.api_key_hash = hash_token(api_key)
        if device.status is None:
            device.status = DeviceStatus.PENDING
        await self.session.commit()
        return device, api_key

    async def ingest_heartbeat(self, hb: Heartbeat) -> EdgeDevice | None:
        device = await self.repo.get_by_device_uuid(hb.device_uuid)
        if device is None:
            return None
        was_online = device.status == DeviceStatus.ONLINE
        device.status = DeviceStatus.ONLINE
        device.last_seen = datetime.now(UTC)
        for field in ("cpu_usage", "memory_usage", "gpu_usage", "gpu_memory_usage", "temperature",
                      "agent_version", "hostname", "ip_address", "gpu_name", "gpu_memory"):
            value = getattr(hb, field)
            if value is not None:
                setattr(device, field, value)
        await self.session.commit()

        settings = get_settings()
        await get_redis().set(
            HEARTBEAT_CACHE_KEY.format(uuid=hb.device_uuid),
            hb.model_dump_json(),
            ex=settings.device_offline_after_seconds * 3,
        )
        payload = {"device_id": str(device.id), **json.loads(hb.model_dump_json())}
        await broadcaster.publish(RealtimeEventType.DEVICE_HEARTBEAT, payload)
        if not was_online:
            await self._publish_status(device)
        return device

    async def ingest_status(self, status: DeviceStatusPayload) -> EdgeDevice | None:
        device = await self.repo.get_by_device_uuid(status.device_uuid)
        if device is None:
            return None
        device.status = DeviceStatus.ONLINE if status.state == DeviceState.ONLINE else DeviceStatus.OFFLINE
        if status.state == DeviceState.ONLINE:
            device.last_seen = datetime.now(UTC)

        changed_cameras = []
        if status.cameras or status.state == DeviceState.OFFLINE:
            cams = {str(c.id): c for c in await self.cameras.list_for_device(device.id)}
            reported = {c.camera_id: c for c in status.cameras}
            for cam_id, cam in cams.items():
                if status.state == DeviceState.OFFLINE:
                    new = CameraStatus.OFFLINE
                elif cam_id in reported:
                    new = CameraStatus(reported[cam_id].state.value)
                else:
                    continue
                if cam.status != new:
                    cam.status = new
                    changed_cameras.append(
                        {"camera_id": cam_id, "status": new.value,
                         "error": reported[cam_id].error if cam_id in reported else None}
                    )
        await self.session.commit()

        await self._publish_status(device)
        for cam in changed_cameras:
            await broadcaster.publish(RealtimeEventType.CAMERA_STATUS, {"device_id": str(device.id), **cam})
        return device

    async def mark_stale_offline(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().device_offline_after_seconds)
        rows = await self.repo.mark_stale_offline(cutoff)
        await self.session.commit()
        for device_id, device_uuid in rows:
            await broadcaster.publish(
                RealtimeEventType.DEVICE_STATUS,
                {"device_id": str(device_id), "device_uuid": device_uuid, "status": DeviceStatus.OFFLINE.value},
            )
        return len(rows)

    async def _publish_status(self, device: EdgeDevice) -> None:
        await broadcaster.publish(
            RealtimeEventType.DEVICE_STATUS,
            {
                "device_id": str(device.id),
                "device_uuid": device.device_uuid,
                "status": device.status.value,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            },
        )
