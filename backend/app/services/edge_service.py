"""Device-facing operations: configuration delivery and snapshot upload URLs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared import topics
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.messaging import publisher
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.repositories.camera_repository import CameraRepository
from app.schemas.camera import CameraCreate
from app.schemas.edge import (
    EdgeCameraConfig,
    EdgeCameraSync,
    EdgeCameraSyncResult,
    EdgeConfig,
    EdgeModelConfig,
    EdgeMQTTConfig,
    EdgeStreamingConfig,
    EdgeVideoConfig,
    PresignResponse,
)
from app.services import storage_service
from app.services.camera_service import CameraService, build_authenticated_url
from app.services.connection_history import ConnectionHistory

PRESIGN_TTL_SECONDS = 300


def _parse_resolution(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    w, _, h = value.partition("x")
    return int(w), int(h)


def _camera_config(c: Camera) -> EdgeCameraConfig:
    width, height = _parse_resolution(c.resolution)
    return EdgeCameraConfig(
        id=c.id,
        camera_id=c.code,
        name=c.name,
        rtsp_url=build_authenticated_url(c),
        onvif_url=c.onvif_url,
        enabled=c.enabled,
        ai_enabled=c.ai_enabled,
        stream_enabled=c.stream_enabled,
        annotated_stream_enabled=c.annotated_stream_enabled,
        original_stream_enabled=c.original_stream_enabled,
        stream_path=c.stream_path,
        original_stream_path=c.original_stream_path,
        video=EdgeVideoConfig(
            video_codec=c.video_codec,
            width=width,
            height=height,
            stream_fps=c.stream_fps,
            inference_fps=c.inference_fps,
            bitrate=c.bitrate,
            gop_size=c.gop_size,
        ),
        ai_model=EdgeModelConfig.model_validate(c.ai_model, from_attributes=True) if c.ai_model else None,
    )


class EdgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cameras = CameraRepository(session)

    async def build_config(self, device: EdgeDevice) -> EdgeConfig:
        settings = get_settings()
        cameras = await self.cameras.list_for_device(device.id)
        timestamps = [device.updated_at, *(c.updated_at for c in cameras)]
        version = int(max(t.timestamp() for t in timestamps if t is not None))
        return EdgeConfig(
            device_uuid=device.device_uuid,
            version=version,
            cameras=[_camera_config(c) for c in cameras],
            mqtt=EdgeMQTTConfig(
                host=settings.mqtt_public_host,
                port=settings.mqtt_public_port,
                tls=settings.mqtt_tls,
                topics={
                    "heartbeat": topics.heartbeat(device.device_uuid),
                    "status": topics.status(device.device_uuid),
                    "events": topics.device_events(device.device_uuid),
                    "camera_events": topics.camera_events(device.device_uuid, "{camera_id}"),
                    "camera_status": topics.camera_status(device.device_uuid, "{camera_id}"),
                    "logs": topics.device_logs(device.device_uuid),
                    "camera_logs": topics.camera_logs(device.device_uuid, "{camera_id}"),
                    "command": topics.command(device.device_uuid),
                    "config": topics.config(device.device_uuid),
                },
            ),
            streaming=EdgeStreamingConfig(
                protocol=settings.edge_stream_protocol,
                rtsp_publish_url=settings.mediamtx_rtsp_publish_url,
                srt_publish_url=settings.mediamtx_srt_publish_url,
            ),
        )

    async def presign_snapshot(
        self, device: EdgeDevice, camera_id: uuid.UUID | None = None, camera_code: str | None = None
    ) -> PresignResponse:
        part: uuid.UUID | str = "device"
        if camera_id is not None or camera_code is not None:
            camera = (
                await self.cameras.get(camera_id)
                if camera_id is not None
                else await self.cameras.get_by_device_code(device.id, camera_code or "")
            )
            if camera is None or camera.edge_device_id != device.id:
                raise NotFoundError("camera not found for this device")
            part = camera.id
        key = storage_service.build_snapshot_key(device.device_uuid, part)
        return PresignResponse(
            object_key=key,
            upload_url=storage_service.presign_upload(key, PRESIGN_TTL_SECONDS),
            expires_in=PRESIGN_TTL_SECONDS,
        )

    async def _announce(self, device: EdgeDevice, code: str, name: str | None) -> tuple[uuid.UUID, str | None]:
        """Create / rename / restore one edge-managed camera. Returns (camera id, "added" | "restored" | None)."""
        camera = await self.cameras.get_by_device_code(device.id, code)
        if camera is None:
            created = await CameraService(self.session).create(
                CameraCreate(edge_device_id=device.id, code=code, name=name or code)
            )
            return created.id, "added"
        change = None
        if name and camera.name != name:
            camera.name = name
        if camera.missing_from_edge_at is not None:
            # listed again: undo what the sync did when it went missing
            camera.missing_from_edge_at = None
            camera.enabled = True
            change = "restored"
        await self.session.commit()
        return camera.id, change

    async def declare_camera(self, device: EdgeDevice, code: str, name: str | None) -> EdgeCameraConfig:
        """Create (or rename) a camera announced by the edge itself; its source stays on the edge."""
        camera_id, change = await self._announce(device, code, name)
        if change:
            await ConnectionHistory(self.session).camera_sync(device, [code] if change == "added" else [],
                                                              [code] if change == "restored" else [], [])
        full = await self.cameras.get_full(camera_id)
        assert full is not None
        return _camera_config(full)

    async def sync_cameras(self, device: EdgeDevice, body: EdgeCameraSync) -> EdgeCameraSyncResult:
        """The edge sends its complete camera list.

        Listed cameras are created / renamed / restored. Edge-managed cameras (no source configured on the
        platform) that are not listed any more are disabled and flagged, never deleted: history is kept and
        they come back automatically when listed again. Cameras whose source the platform configures (the
        AIVMS edge-agent) are never touched by a sync.
        """
        added: list[str] = []
        restored: list[str] = []
        ids: list[uuid.UUID] = []
        for item in body.cameras:
            camera_id, change = await self._announce(device, item.code, item.name)
            ids.append(camera_id)
            if change == "added":
                added.append(item.code)
            elif change == "restored":
                restored.append(item.code)

        listed = {c.code for c in body.cameras}
        now = datetime.now(UTC)
        missing: list[str] = []
        for camera in await self.cameras.list_for_device(device.id):
            if camera.code in listed or camera.rtsp_url or camera.missing_from_edge_at is not None:
                continue
            camera.missing_from_edge_at = now
            camera.enabled = False
            missing.append(camera.code)
        await self.session.commit()

        if added or restored or missing:
            await ConnectionHistory(self.session).camera_sync(device, added, restored, missing)
            await publisher.notify_config_changed(device.device_uuid, "camera_sync")
        configs = []
        for camera_id in ids:
            full = await self.cameras.get_full(camera_id)
            if full is not None:
                configs.append(_camera_config(full))
        return EdgeCameraSyncResult(cameras=configs, added=added, restored=restored, missing=missing)
