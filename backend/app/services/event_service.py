from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aivms_shared.payloads import DetectionEvent as DetectionPayload
from app.core.exceptions import NotFoundError
from app.realtime.broadcaster import broadcaster
from app.realtime.messages import RealtimeEventType
from app.repositories.ai_model_repository import AIModelRepository
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.event_repository import EventRepository
from app.schemas.common import Page, PageParams
from app.schemas.detection_event import DetectionEventRead, EventFilter
from app.services import storage_service
from app.services.mappers import event_to_read

logger = logging.getLogger(__name__)


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EventRepository(session)
        self.devices = DeviceRepository(session)
        self.cameras = CameraRepository(session)
        self.models = AIModelRepository(session)

    async def list(self, params: PageParams, filters: EventFilter) -> Page[DetectionEventRead]:
        rows, total = await self.repo.paginate(self.repo.list_stmt(filters), params.offset, params.page_size)
        return Page(items=[event_to_read(e) for e in rows], total=total, page=params.page, page_size=params.page_size)

    async def get(self, event_id: uuid.UUID) -> DetectionEventRead:
        event = await self.repo.get_full(event_id)
        if not event:
            raise NotFoundError("event not found")
        return event_to_read(event)

    async def delete(self, event_id: uuid.UUID) -> None:
        event = await self.repo.get(event_id)
        if not event:
            raise NotFoundError("event not found")
        await self.repo.delete(event)
        await self.session.commit()

    async def classes(self) -> list[str]:
        return await self.repo.distinct_classes()

    async def ingest(self, payload: DetectionPayload, topic_device_id: str) -> int:
        """MQTT -> DB -> WebSocket. Returns number of rows inserted (0 for duplicates/invalid)."""
        if payload.device_id != topic_device_id:
            logger.warning("device_id mismatch topic=%s payload=%s; dropped", topic_device_id, payload.device_id)
            return 0
        device = await self.devices.get_by_device_uuid(payload.device_id)
        if device is None:
            logger.warning("event from unknown device %s dropped", payload.device_id)
            return 0

        # camera_id in MQTT is the camera code (unique per device); a UUID is accepted as well
        camera = await self.cameras.get_by_device_code(device.id, payload.camera_id)
        if camera is None:
            try:
                camera = await self.cameras.get(uuid.UUID(payload.camera_id))
            except ValueError:
                camera = None
        if camera is None or camera.edge_device_id != device.id:
            logger.warning("event for unknown/foreign camera %s dropped", payload.camera_id)
            return 0

        model = await self.models.resolve(payload.model) if payload.model else None
        snapshot_key = payload.snapshot_key
        if snapshot_key and not storage_service.key_belongs_to_device(snapshot_key, device.device_uuid):
            logger.warning("snapshot key %s rejected for device %s", snapshot_key, device.device_uuid)
            snapshot_key = None

        detected_at = payload.timestamp if payload.timestamp.tzinfo else payload.timestamp.replace(tzinfo=UTC)
        rows = [
            {
                "id": uuid.uuid4(),
                "event_group_id": payload.event_id,
                "detection_index": idx,
                "camera_id": camera.id,
                "edge_device_id": device.id,
                "ai_model_id": model.id if model else None,
                "track_id": det.track_id,
                "class_name": det.class_name,
                "confidence": det.confidence,
                "bbox": det.bbox.model_dump(),
                "detected_at": detected_at,
                "snapshot_url": snapshot_key,
                "metadata": {
                    **payload.metadata,
                    "class_id": det.class_id,
                    "model": payload.model,
                    "frame": payload.frame.model_dump() if payload.frame else None,
                    "attributes": det.attributes,
                },
                "created_at": datetime.now(UTC),
            }
            for idx, det in enumerate(payload.detections)
        ]
        inserted = await self.repo.insert_many_idempotent(rows)
        await self.session.commit()

        for event in inserted:
            await broadcaster.publish(
                RealtimeEventType.DETECTION_CREATED, event_to_read(event).model_dump(mode="json")
            )
        return len(inserted)
