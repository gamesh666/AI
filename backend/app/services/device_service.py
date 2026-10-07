from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared import topics
from aivms_shared.payloads import CameraRuntimeStatus, CommandType, DeviceState, Heartbeat
from aivms_shared.payloads import DeviceStatus as DeviceStatusPayload
from app.core.config import get_settings
from app.core.enums import CameraStatus, DeviceStatus, StreamStatus
from app.core.exceptions import AuthError, ConflictError, DomainError, NotFoundError
from app.core.redis import get_redis
from app.core.security import constant_time_equals, generate_opaque_token, hash_token
from app.messaging import publisher
from app.models.edge_device import EdgeDevice
from app.realtime.broadcaster import broadcaster
from app.realtime.messages import RealtimeEventType
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.edge_log_repository import EdgeLogRepository
from app.schemas.common import Page, PageParams
from app.schemas.edge import EdgeRegisterRequest
from app.schemas.edge_device import (
    EdgeConnectionInfo,
    EdgeDeviceCreate,
    EdgeDeviceRead,
    EdgeDeviceUpdate,
    EdgeDeviceWithKey,
)
from app.services.camera_service import CameraService
from app.services.connection_history import (
    CONNECTION,
    REASON_EDGE_REPORTED,
    REASON_HEARTBEAT_TIMEOUT,
    ConnectionHistory,
)
from app.services.mappers import device_to_read

HEARTBEAT_CACHE_KEY = "aivms:device:{uuid}:heartbeat"


def _camera_status_message(device: EdgeDevice, camera) -> dict:
    return {
        "device_id": str(device.id),
        "camera_id": str(camera.id),
        "camera_code": camera.code,
        "status": camera.status.value,
        "stream_status": camera.stream_status.value,
        "ai_status": camera.ai_status,
        "last_frame_at": camera.last_frame_at.isoformat() if camera.last_frame_at else None,
        "runtime_stats": camera.runtime_stats or {},
    }



def connection_info(device_uuid: str, include_mqtt_password: bool) -> EdgeConnectionInfo:
    """What to hand to whoever sets up the edge (the device key is returned separately, once)."""
    s = get_settings()
    password = s.mqtt_edge_password.get_secret_value() if include_mqtt_password and s.mqtt_edge_password else None
    return EdgeConnectionInfo(
        device_id=device_uuid,
        mqtt_host=s.mqtt_public_host,
        mqtt_port=s.mqtt_public_port,
        mqtt_tls=s.mqtt_tls,
        mqtt_username=s.mqtt_edge_username,
        mqtt_password=password,
        stream_protocol=s.edge_stream_protocol,
        rtsp_publish_url=s.mediamtx_rtsp_publish_url,
        srt_publish_url=s.mediamtx_srt_publish_url,
        snapshot_upload_url=s.minio_edge_url,
        topics={
            "heartbeat": topics.heartbeat(device_uuid),
            "status": topics.status(device_uuid),
            "camera_status": topics.camera_status(device_uuid, "{camera_id}"),
            "camera_logs": topics.camera_logs(device_uuid, "{camera_id}"),
            "logs": topics.device_logs(device_uuid),
            "camera_events": topics.camera_events(device_uuid, "{camera_id}"),
            "command": topics.command(device_uuid),
        },
    )


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
        ids = [d.id for d in rows]
        counts = await self.repo.camera_counts(ids)
        outages = await EdgeLogRepository(self.session).counts_by_device(
            CONNECTION, datetime.now(UTC) - timedelta(hours=24), ids
        )
        return Page(
            items=[device_to_read(d, counts.get(d.id, 0), outages.get(d.id, 0)) for d in rows],
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

    async def create(self, data: EdgeDeviceCreate, include_mqtt_password: bool = False) -> EdgeDeviceWithKey:
        api_key = generate_opaque_token()
        device = EdgeDevice(**data.model_dump(), api_key_hash=hash_token(api_key), status=DeviceStatus.PENDING)
        try:
            await self.repo.add(device)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("device_uuid already exists") from exc
        await self.session.refresh(device, ["site"])
        return EdgeDeviceWithKey(
            **device_to_read(device).model_dump(),
            api_key=api_key,
            connection=connection_info(device.device_uuid, include_mqtt_password),
        )

    async def update(self, device_id: uuid.UUID, data: EdgeDeviceUpdate) -> EdgeDeviceRead:
        device = await self.get(device_id)
        changes = data.model_dump(exclude_unset=True)
        site_changed = "site_id" in changes and changes["site_id"] != device.site_id
        self.repo.apply_updates(device, changes)
        if site_changed:
            await self.session.flush()
            # stream paths embed the site code: ai/<site>/<device>/<camera>
            await CameraService(self.session).refresh_stream_paths(device)
        await self.session.commit()
        if site_changed:
            await publisher.notify_config_changed(device.device_uuid, "site_changed")
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
        # rotating is admin-only, so the MQTT password may be included
        return EdgeDeviceWithKey(
            **read.model_dump(), api_key=api_key, connection=connection_info(device.device_uuid, True)
        )

    async def connection(self, device_id: uuid.UUID) -> EdgeConnectionInfo:
        device = await self.get(device_id)
        return connection_info(device.device_uuid, True)

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
        previous = device.status
        was_online = previous == DeviceStatus.ONLINE
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
        if previous == DeviceStatus.OFFLINE:
            await ConnectionHistory(self.session).device_online(device)
        return device

    async def ingest_status(self, status: DeviceStatusPayload) -> EdgeDevice | None:
        """Device-level online/offline (retained message + MQTT Last Will)."""
        device = await self.repo.get_by_device_uuid(status.device_uuid)
        if device is None:
            return None
        online = status.state == DeviceState.ONLINE
        previous = device.status
        device.status = DeviceStatus.ONLINE if online else DeviceStatus.OFFLINE
        changed_cameras = []
        if online:
            device.last_seen = datetime.now(UTC)
        else:
            changed_cameras = await self._mark_cameras_offline(device)
        await self.session.commit()

        await self._publish_status(device)
        for payload in changed_cameras:
            await broadcaster.publish(RealtimeEventType.CAMERA_STATUS, payload)
        history = ConnectionHistory(self.session)
        if online and previous == DeviceStatus.OFFLINE:
            await history.device_online(device)
        elif not online and previous == DeviceStatus.ONLINE:
            await history.device_offline(device, REASON_EDGE_REPORTED)
        return device

    async def ingest_camera_status(self, device_uuid: str, status: CameraRuntimeStatus) -> bool:
        """Per-camera health from edge/{device}/cameras/{camera}/status."""
        device = await self.repo.get_by_device_uuid(device_uuid)
        if device is None:
            return False
        camera = await self.cameras.get_by_device_code(device.id, status.camera_id)
        if camera is None:
            return False
        camera.status = CameraStatus(status.rtsp_status.value)
        camera.stream_status = StreamStatus(status.stream_status.value)
        camera.ai_status = status.ai_status.value
        if status.last_frame_at:
            camera.last_frame_at = status.last_frame_at
        camera.runtime_stats = {
            "input_fps": status.input_fps,
            "inference_fps": status.inference_fps,
            "output_fps": status.output_fps,
            "resolution": status.resolution,
            "dropped_frames": status.dropped_frames,
            "error": status.error,
            "reported_at": status.timestamp.isoformat(),
        }
        await self.session.commit()
        await broadcaster.publish(RealtimeEventType.CAMERA_STATUS, _camera_status_message(device, camera))
        return True

    async def _mark_cameras_offline(self, device: EdgeDevice) -> list[dict]:
        changed = []
        for cam in await self.cameras.list_for_device(device.id):
            if cam.status != CameraStatus.OFFLINE or cam.stream_status != StreamStatus.OFFLINE:
                cam.status = CameraStatus.OFFLINE
                cam.stream_status = StreamStatus.OFFLINE
                changed.append(_camera_status_message(device, cam))
        return changed

    async def mark_stale_offline(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().device_offline_after_seconds)
        rows = await self.repo.mark_stale_offline(cutoff)
        camera_updates = []
        for device_id, _ in rows:
            device = await self.repo.get(device_id)
            if device is not None:
                camera_updates.extend(await self._mark_cameras_offline(device))
        await self.session.commit()
        for payload in camera_updates:
            await broadcaster.publish(RealtimeEventType.CAMERA_STATUS, payload)
        for device_id, device_uuid in rows:
            await broadcaster.publish(
                RealtimeEventType.DEVICE_STATUS,
                {"device_id": str(device_id), "device_uuid": device_uuid, "status": DeviceStatus.OFFLINE.value},
            )
        history = ConnectionHistory(self.session)
        for device_id, _ in rows:
            if (device := await self.repo.get(device_id)) is not None:
                await history.device_offline(device, REASON_HEARTBEAT_TIMEOUT)
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
