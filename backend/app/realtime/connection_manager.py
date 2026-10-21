"""Tracks WebSocket connections that belong to THIS backend instance."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.realtime.messages import RealtimeEventType

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class Client:
    websocket: WebSocket
    user_id: str
    # empty set = receive every event type
    subscriptions: set[RealtimeEventType] = field(default_factory=set)

    def wants(self, event_type: str) -> bool:
        return not self.subscriptions or event_type in self.subscriptions


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[Client] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, client: Client) -> None:
        async with self._lock:
            self._clients.add(client)
        logger.info("ws connected user=%s total=%d", client.user_id, self.count)

    async def disconnect(self, client: Client) -> None:
        async with self._lock:
            self._clients.discard(client)
        logger.info("ws disconnected user=%s total=%d", client.user_id, self.count)

    async def broadcast_raw(self, event_type: str, text: str) -> None:
        """Send a pre-serialized message to every interested local client."""
        async with self._lock:
            targets = [c for c in self._clients if c.wants(event_type)]
        if not targets:
            return
        results = await asyncio.gather(
            *(c.websocket.send_text(text) for c in targets), return_exceptions=True
        )
        for client, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                await self.disconnect(client)
