"""Cross-instance fan-out via Redis Pub/Sub.

publish()  -> Redis channel  -> every backend instance's listener -> local WebSocket clients

Because nothing about a connection is shared between instances, backends can be scaled horizontally.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.redis import get_redis
from app.realtime.connection_manager import ConnectionManager
from app.realtime.messages import RealtimeEventType, RealtimeMessage

logger = logging.getLogger(__name__)

CHANNEL = "aivms:realtime"


class RealtimeBroadcaster:
    def __init__(self, manager: ConnectionManager, channel: str = CHANNEL) -> None:
        self.manager = manager
        self.channel = channel
        self._task: asyncio.Task | None = None

    async def publish(self, event_type: RealtimeEventType, data: dict[str, Any]) -> None:
        message = RealtimeMessage(type=event_type, data=data)
        try:
            await get_redis().publish(self.channel, message.model_dump_json())
        except Exception:  # realtime is best-effort; never break the ingest path
            logger.exception("failed to publish realtime message")

    async def _listen(self) -> None:
        while True:
            try:
                pubsub = get_redis().pubsub()
                await pubsub.subscribe(self.channel)
                logger.info("realtime listener subscribed to %s", self.channel)
                async for item in pubsub.listen():
                    if item.get("type") != "message":
                        continue
                    text = item["data"]
                    try:
                        event_type = json.loads(text).get("type", "")
                    except ValueError:
                        continue
                    await self.manager.broadcast_raw(event_type, text)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("realtime listener error, retrying in 3s")
                await asyncio.sleep(3)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._listen(), name="realtime-listener")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


# process-wide singletons
connection_manager = ConnectionManager()
broadcaster = RealtimeBroadcaster(connection_manager)
