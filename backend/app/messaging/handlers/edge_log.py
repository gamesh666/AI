from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import EdgeLog
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.edge_log_service import EdgeLogService

logger = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 256 * 1024


async def handle_edge_log(msg: IncomingMessage) -> None:
    """edge/{d}/logs and edge/{d}/cameras/{c}/logs — any recognition result or log line."""
    parsed = topics.parse(msg.topic)
    if parsed is None or not msg.payload:
        return
    if len(msg.payload) > MAX_MESSAGE_BYTES:
        logger.warning("log on %s too large (%d bytes); dropped", msg.topic, len(msg.payload))
        return
    log = parse_payload(msg, EdgeLog)
    if log is None:
        return
    if parsed.camera_id:
        if log.camera_id is None:
            log.camera_id = parsed.camera_id
        elif log.camera_id != parsed.camera_id:
            logger.warning("camera mismatch topic=%s payload=%s; dropped", parsed.camera_id, log.camera_id)
            return
    async with get_session_factory()() as session:
        await EdgeLogService(session).ingest(log, parsed.device_id)
