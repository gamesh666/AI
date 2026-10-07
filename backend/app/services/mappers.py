"""ORM -> DTO mapping that needs joined data or must hide sensitive fields."""

from __future__ import annotations

from app.models.camera import Camera
from app.models.detection_event import DetectionEvent
from app.models.edge_device import EdgeDevice
from app.schemas.camera import CameraRead
from app.schemas.detection_event import DetectionEventRead
from app.schemas.edge_device import EdgeDeviceRead
from app.services import storage_service


def device_to_read(device: EdgeDevice, camera_count: int = 0, disconnects_24h: int = 0) -> EdgeDeviceRead:
    dto = EdgeDeviceRead.model_validate(device)
    dto.site_name = device.site.name if device.site else None
    dto.camera_count = camera_count
    dto.disconnects_24h = disconnects_24h
    return dto


def camera_to_read(camera: Camera) -> CameraRead:
    device = camera.edge_device
    site = device.site if device else None
    return CameraRead(
        id=camera.id,
        code=camera.code,
        edge_device_id=camera.edge_device_id,
        edge_device_uuid=device.device_uuid if device else None,
        edge_device_name=device.name if device else None,
        edge_device_status=device.status.value if device else None,
        site_id=site.id if site else None,
        site_code=site.code if site else None,
        site_name=site.name if site else None,
        name=camera.name,
        # the source address stays on the edge side: only say whether it is configured
        source_configured=bool(camera.rtsp_url),
        has_credentials=bool(camera.rtsp_username or camera.rtsp_password_encrypted),
        enabled=camera.enabled,
        ai_enabled=camera.ai_enabled,
        stream_enabled=camera.stream_enabled,
        annotated_stream_enabled=camera.annotated_stream_enabled,
        original_stream_enabled=camera.original_stream_enabled,
        ai_model_id=camera.ai_model_id,
        ai_model_name=camera.ai_model.name if camera.ai_model else None,
        stream_path=camera.stream_path,
        resolution=camera.resolution,
        stream_fps=camera.stream_fps,
        inference_fps=camera.inference_fps,
        bitrate=camera.bitrate,
        gop_size=camera.gop_size,
        status=camera.status,
        stream_status=camera.stream_status,
        ai_status=camera.ai_status,
        last_frame_at=camera.last_frame_at,
        runtime_stats=camera.runtime_stats or {},
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
        track_id=event.track_id,
        class_name=event.class_name,
        confidence=event.confidence,
        bbox=event.bbox,
        detected_at=event.detected_at,
        snapshot_url=storage_service.presign_download(event.snapshot_url),
        metadata=event.extra or {},
    )
