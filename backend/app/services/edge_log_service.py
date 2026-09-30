from __future__ import annotations

import logging
import uuid
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared.payloads import EdgeLog as EdgeLogPayload
from app.core.exceptions import NotFoundError
from app.models.edge_log import EdgeLog
from app.realtime.broadcaster import broadcaster
from app.realtime.messages import RealtimeEventType
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.edge_log_repository import EdgeLogRepository
from app.schemas.common import Page, PageParams
from app.schemas.edge_log import EdgeLogFilter, EdgeLogRead
from app.services import storage_service

logger = logging.getLogger(__name__)

# upper bound for the free-form part of one log (the MQTT message itself is capped by the handler)
MAX_DATA_BYTES = 64 * 1024


def log_to_read(log: EdgeLog) -> EdgeLogRead:
    device = log.edge_device
    site = device.site if device else None
    return EdgeLogRead(
        id=log.id,
        event_id=log.event_id,
        edge_device_id=log.edge_device_id,
        edge_device_uuid=device.device_uuid if device else None,
        edge_device_name=device.name if device else None,
        site_id=site.id if site else None,
        site_name=site.name if site else None,
        camera_id=log.camera_id,
        camera_code=log.camera_code,
        camera_name=log.camera.name if log.camera else None,
        event_type=log.event_type,
        severity=log.severity,
        status=log.status,
        message=log.message,
        data=log.data or {},
        detections=log.detections or [],
        frame=log.frame,
        snapshot_url=storage_service.presign_download(log.snapshot_key),
        occurred_at=log.occurred_at,
        updated_at=log.updated_at,
    )


class EdgeLogService:
    """Stores and serves whatever edges report. The platform never interprets type or data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EdgeLogRepository(session)
        self.devices = DeviceRepository(session)
        self.cameras = CameraRepository(session)

    async def list(self, params: PageParams, filters: EdgeLogFilter) -> Page[EdgeLogRead]:
        rows, total = await self.repo.paginate(self.repo.list_stmt(filters), params.offset, params.page_size)
        return Page(items=[log_to_read(r) for r in rows], total=total, page=params.page, page_size=params.page_size)

    async def get(self, log_id: uuid.UUID) -> EdgeLogRead:
        log = await self.repo.get_full(log_id)
        if not log:
            raise NotFoundError("log not found")
        return log_to_read(log)

    async def delete(self, log_id: uuid.UUID) -> None:
        log = await self.repo.get(log_id)
        if not log:
            raise NotFoundError("log not found")
        await self.repo.delete(log)
        await self.session.commit()

    async def types(self) -> list[str]:
        return await self.repo.distinct_types()

    async def ingest(self, payload: EdgeLogPayload, topic_device_id: str) -> EdgeLogRead | None:
        """MQTT -> DB (insert or update by event_id) -> WebSocket."""
        if payload.device_id != topic_device_id:
            logger.warning("log device mismatch topic=%s payload=%s; dropped", topic_device_id, payload.device_id)
            return None
        device = await self.devices.get_by_device_uuid(payload.device_id)
        if device is None:
            logger.warning("log from unknown device %s dropped", payload.device_id)
            return None
        data_size = len(payload.model_dump_json(include={"data"}))
        if data_size > MAX_DATA_BYTES:
            logger.warning("log %s from %s: data too large (%d bytes); dropped", payload.event_id, device.device_uuid,
                           data_size)
            return None

        # an unknown camera code is kept as text: the log is still worth storing
        camera = await self.cameras.get_by_device_code(device.id, payload.camera_id) if payload.camera_id else None
        snapshot_key = payload.snapshot_key
        if snapshot_key and not storage_service.key_belongs_to_device(snapshot_key, device.device_uuid):
            logger.warning("snapshot key %s rejected for device %s", snapshot_key, device.device_uuid)
            snapshot_key = None

        occurred_at = payload.timestamp if payload.timestamp.tzinfo else payload.timestamp.replace(tzinfo=UTC)
        row = {
            "id": uuid.uuid4(),
            "event_id": payload.event_id,
            "edge_device_id": device.id,
            "camera_id": camera.id if camera else None,
            "camera_code": payload.camera_id,
            "event_type": payload.event_type,
            "severity": payload.severity.value,
            "status": payload.status,
            "message": payload.message,
            "data": payload.data,
            "detections": [d.model_dump(mode="json") for d in payload.detections],
            "frame": payload.frame.model_dump() if payload.frame else None,
            "snapshot_key": snapshot_key,
            "occurred_at": occurred_at,
        }
        provided = set(payload.model_fields_set)
        if "camera_id" in provided:
            provided.add("camera_code")
        if "snapshot_key" in provided and snapshot_key is None:
            provided.discard("snapshot_key")  # a rejected key never wipes a good one
        log, created = await self.repo.upsert(row, provided)
        await self.session.commit()

        read = log_to_read(log)
        await broadcaster.publish(
            RealtimeEventType.LOG_CREATED if created else RealtimeEventType.LOG_UPDATED,
            read.model_dump(mode="json"),
        )
        return read
