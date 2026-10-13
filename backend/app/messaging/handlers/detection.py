from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import DetectionEvent
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.edge_log_service import EdgeLogService, detection_to_log

logger = logging.getLogger(__name__)


async def handle_detection(msg: IncomingMessage) -> None:
    """edge/{d}/events and edge/{d}/cameras/{c}/events (edge-agent format) -> stored as an Edge log."""
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
        await EdgeLogService(session).ingest(detection_to_log(event), parsed.device_id)
