from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import Heartbeat
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)


async def handle_heartbeat(msg: IncomingMessage) -> None:
    parsed = topics.parse(msg.topic)
    hb = parse_payload(msg, Heartbeat)
    if parsed is None or hb is None:
        return
    if hb.device_uuid != parsed.device_id:
        logger.warning("heartbeat device mismatch topic=%s payload=%s", parsed.device_id, hb.device_uuid)
        return
    async with get_session_factory()() as session:
        if await DeviceService(session).ingest_heartbeat(hb) is None:
            logger.info("heartbeat from unregistered device %s ignored", hb.device_uuid)
