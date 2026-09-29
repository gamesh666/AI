"""ORM -> DTO mapping that needs joined data or must hide sensitive fields."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from app.models.camera import Camera
from app.models.detection_event import DetectionEvent
from app.models.edge_device import EdgeDevice
from app.schemas.camera import CameraRead
from app.schemas.detection_event import DetectionEventRead
from app.schemas.edge_device import EdgeDeviceRead
from app.services import storage_service


def mask_rtsp_url(url: str) -> str:
    """Remove any userinfo from a URL (defence in depth — stored URLs are already clean)."""
    parts = urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        parts = parts._replace(netloc=host)
    return urlunsplit(parts)


def device_to_read(device: EdgeDevice, camera_count: int = 0) -> EdgeDeviceRead:
    dto = EdgeDeviceRead.model_validate(device)
    dto.site_name = device.site.name if device.site else None
    dto.camera_count = camera_count
    return dto


def camera_to_read(camera: Camera) -> CameraRead:
    device = camera.edge_device
    site = device.site if device else None
    return CameraRead(
        id=camera.id,
        edge_device_id=camera.edge_device_id,
        edge_device_name=device.name if device else None,
        edge_device_status=device.status.value if device else None,
        site_id=site.id if site else None,
        site_name=site.name if site else None,
        name=camera.name,
        rtsp_url_masked=mask_rtsp_url(camera.rtsp_url),
        has_credentials=bool(camera.rtsp_username or camera.rtsp_password_encrypted),
        onvif_url=camera.onvif_url,
        stream_id=camera.stream_id,
        enabled=camera.enabled,
        ai_enabled=camera.ai_enabled,
        ai_model_id=camera.ai_model_id,
        ai_model_name=camera.ai_model.name if camera.ai_model else None,
        status=camera.status,
        created_at=camera.created_at,
    )


def event_to_read(event: DetectionEvent) -> DetectionEventRead:
    device = event.edge_device
    site = device.site if device else None
    return DetectionEventRead(
        id=event.id,
        event_group_id=event.event_group_id,
        camera_id=event.camera_id,
        camera_name=event.camera.name if event.camera else None,
        edge_device_id=event.edge_device_id,
        edge_device_name=device.name if device else None,
        site_id=site.id if site else None,
        site_name=site.name if site else None,
        ai_model_id=event.ai_model_id,
        ai_model_name=event.ai_model.name if event.ai_model else None,
        class_name=event.class_name,
        confidence=event.confidence,
        bbox=event.bbox,
        detected_at=event.detected_at,
        snapshot_url=storage_service.presign_download(event.snapshot_url),
        metadata=event.extra or {},
    )
