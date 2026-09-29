from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import DetectionEvent
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.event_service import EventService

logger = logging.getLogger(__name__)


async def handle_detection(msg: IncomingMessage) -> None:
    """Handles both edge/{d}/events and edge/{d}/cameras/{c}/events."""
    parsed = topics.parse(msg.topic)
    event = parse_payload(msg, DetectionEvent)
    if parsed is None or event is None:
        return
    if parsed.camera_id and parsed.camera_id != event.camera_id:
        logger.warning("camera mismatch topic=%s payload=%s; dropped", parsed.camera_id, event.camera_id)
        return
    if not event.detections:
        return
    async with get_session_factory()() as session:
        inserted = await EventService(session).ingest(event, parsed.device_id)
    logger.debug("event %s: %d detections stored", event.event_id, inserted)
