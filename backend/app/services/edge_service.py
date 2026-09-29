"""Device-facing operations: configuration delivery and snapshot upload URLs."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared import topics
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.repositories.camera_repository import CameraRepository
from app.schemas.edge import (
    EdgeCameraConfig,
    EdgeConfig,
    EdgeModelConfig,
    EdgeMQTTConfig,
    EdgeStreamingConfig,
    EdgeVideoConfig,
    PresignResponse,
)
from app.services import storage_service
from app.services.camera_service import build_authenticated_url

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

    async def presign_snapshot(self, device: EdgeDevice, camera_id: uuid.UUID) -> PresignResponse:
        camera = await self.cameras.get(camera_id)
        if camera is None or camera.edge_device_id != device.id:
            raise NotFoundError("camera not found for this device")
        key = storage_service.build_snapshot_key(device.device_uuid, camera_id)
        return PresignResponse(
            object_key=key,
            upload_url=storage_service.presign_upload(key, PRESIGN_TTL_SECONDS),
            expires_in=PRESIGN_TTL_SECONDS,
        )
