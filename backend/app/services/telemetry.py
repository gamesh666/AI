"""What the platform tells an edge, carried back in the answer to its heartbeat (POST /edge/heartbeat).

- commands        queued in Redis, delivered once by the next heartbeat
- config_version  bumped on every platform-side config change; the edge re-fetches GET /edge/config when
                  it differs from the previous answer
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from aivms_shared.payloads import Command
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# API paths (relative to the API base URL) of the edge telemetry endpoints
HTTP_PATHS = {
    "heartbeat": "/edge/heartbeat",
    "status": "/edge/status",
    "camera_status": "/edge/cameras/{camera_id}/status",
    "logs": "/edge/logs",
    "report_options": "/edge/report-options",
}

COMMAND_QUEUE_KEY = "aivms:device:{uuid}:commands"
CONFIG_VERSION_KEY = "aivms:device:{uuid}:config_version"
COMMAND_QUEUE_MAX = 50
COMMAND_TTL_SECONDS = 24 * 3600
COMMANDS_PER_HEARTBEAT = 20


async def queue_command(device_uuid: str, command: Command) -> None:
    key = COMMAND_QUEUE_KEY.format(uuid=device_uuid)
    redis = get_redis()
    await redis.rpush(key, command.model_dump_json())
    await redis.ltrim(key, -COMMAND_QUEUE_MAX, -1)
    await redis.expire(key, COMMAND_TTL_SECONDS)


async def pop_commands(device_uuid: str) -> list[dict]:
    key = COMMAND_QUEUE_KEY.format(uuid=device_uuid)
    raw = await get_redis().lpop(key, COMMANDS_PER_HEARTBEAT)
    return [json.loads(item) for item in raw or []]


async def notify_config_changed(device_uuid: str, reason: str | None = None) -> None:
    """Best effort: the edge sees the new version in its next heartbeat answer and re-fetches its config."""
    try:
        await get_redis().set(CONFIG_VERSION_KEY.format(uuid=device_uuid), int(datetime.now(UTC).timestamp()))
    except Exception:
        logger.exception("failed to record config change (%s) for %s", reason, device_uuid)


async def config_version(device_uuid: str) -> int:
    value = await get_redis().get(CONFIG_VERSION_KEY.format(uuid=device_uuid))
    return int(value) if value else 0
