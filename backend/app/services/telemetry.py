"""Edge telemetry over HTTP, next to MQTT.

Edges may send heartbeat / status / logs either over MQTT (shared broker account) or over HTTPS with their own
device key. For HTTP edges, what MQTT pushes to the device is handed back in the heartbeat answer instead:

- commands      queued in Redis, popped by the next heartbeat
- config change a version number, bumped on every change; the edge re-fetches GET /edge/config when it moves
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from aivms_shared.payloads import Command
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.edge_device import EdgeDevice

# API paths (relative to the API base URL) of the HTTP telemetry endpoints
HTTP_PATHS = {
    "heartbeat": "/edge/heartbeat",
    "status": "/edge/status",
    "camera_status": "/edge/cameras/{camera_id}/status",
    "logs": "/edge/logs",
    "events": "/edge/events",
}

TRANSPORT_MQTT = "mqtt"
TRANSPORT_HTTP = "http"

COMMAND_QUEUE_KEY = "aivms:device:{uuid}:commands"
CONFIG_VERSION_KEY = "aivms:device:{uuid}:config_version"
COMMAND_QUEUE_MAX = 50
COMMAND_TTL_SECONDS = 24 * 3600
COMMANDS_PER_HEARTBEAT = 20
# a transport counts as "in use" while it carried a heartbeat this recently
ACTIVE_WINDOW = timedelta(minutes=5)


def transport_of(device: EdgeDevice, now: datetime | None = None) -> str | None:
    """"http" | "mqtt" | "both" for what the device used recently; None when neither."""
    now = now or datetime.now(UTC)
    used = [name for name, at in ((TRANSPORT_HTTP, device.last_http_at), (TRANSPORT_MQTT, device.last_mqtt_at))
            if at is not None and now - (at if at.tzinfo else at.replace(tzinfo=UTC)) <= ACTIVE_WINDOW]
    if len(used) == 2:
        return "both"
    return used[0] if used else None


def deliver_over_http(device: EdgeDevice) -> bool:
    """Commands go to the heartbeat queue when the shared MQTT account is off or the device only uses HTTP."""
    return not get_settings().mqtt_edge_enabled or transport_of(device) == TRANSPORT_HTTP


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


async def bump_config_version(device_uuid: str, version: int) -> None:
    await get_redis().set(CONFIG_VERSION_KEY.format(uuid=device_uuid), version)


async def config_version(device_uuid: str) -> int:
    value = await get_redis().get(CONFIG_VERSION_KEY.format(uuid=device_uuid))
    return int(value) if value else 0
