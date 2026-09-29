from __future__ import annotations

import logging

from aivms_shared import topics
from aivms_shared.payloads import CameraRuntimeStatus
from app.db.session import get_session_factory
from app.messaging.base import IncomingMessage
from app.messaging.handlers._common import parse_payload
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)


async def handle_camera_status(msg: IncomingMessage) -> None:
    """edge/{device}/cameras/{camera}/status — RTSP / AI / stream health of one camera."""
    parsed = topics.parse(msg.topic)
    if parsed is None or not msg.payload:
        return
    status = parse_payload(msg, CameraRuntimeStatus)
    if status is None or status.camera_id != parsed.camera_id:
        return
    async with get_session_factory()() as session:
        if not await DeviceService(session).ingest_camera_status(parsed.device_id, status):
            logger.debug("status for unknown camera %s/%s ignored", parsed.device_id, parsed.camera_id)
