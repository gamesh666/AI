from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import DeviceStatus
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)


async def handle_status(msg: IncomingMessage) -> None:
    parsed = topics.parse(msg.topic)
    if parsed is None or not msg.payload:  # empty payload = retained message cleared
        return
    status = parse_payload(msg, DeviceStatus)
    if status is None or status.device_uuid != parsed.device_id:
        return
    async with get_session_factory()() as session:
        await DeviceService(session).ingest_status(status)
