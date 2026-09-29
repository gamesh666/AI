"""Server -> Edge messages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aivms_shared import topics
from aivms_shared.payloads import Command, CommandType, ConfigChanged
from app.core.exceptions import DomainError
from app.messaging.runtime import get_broker

logger = logging.getLogger(__name__)


class BrokerUnavailableError(DomainError):
    status_code = 503


async def send_command(device_uuid: str, command: CommandType, params: dict | None = None) -> Command:
    broker = get_broker()
    if broker is None or not broker.connected:
        raise BrokerUnavailableError("message broker is not connected")
    payload = Command(command=command, params=params or {})
    await broker.publish(topics.command(device_uuid), payload.to_bytes(), qos=1)
    return payload


async def notify_config_changed(device_uuid: str, reason: str | None = None) -> None:
    """Best effort: tell the device to re-fetch its config over REST."""
    broker = get_broker()
    if broker is None or not broker.connected:
        logger.warning("broker offline; config change for %s not pushed", device_uuid)
        return
    msg = ConfigChanged(version=int(datetime.now(UTC).timestamp()), reason=reason)
    try:
        await broker.publish(topics.config(device_uuid), msg.to_bytes(), qos=1, retain=True)
    except Exception:
        logger.exception("failed to publish config change for %s", device_uuid)
