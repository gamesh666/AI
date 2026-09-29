"""MQTT implementation of MessageBroker using aiomqtt (paho under the hood).

Works with any MQTT v3.1.1 / v5 broker: Mosquitto (default) or EMQX.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import uuid

import aiomqtt

from app.messaging.base import IncomingMessage, MessageBroker, MessageHandler

logger = logging.getLogger(__name__)


def _strip_share(topic_filter: str) -> str:
    """'$share/group/edge/+/x' -> 'edge/+/x' (matching is done on the real filter)."""
    if topic_filter.startswith("$share/"):
        return topic_filter.split("/", 2)[2]
    return topic_filter


def topic_matches(topic_filter: str, topic: str) -> bool:
    f_parts = _strip_share(topic_filter).split("/")
    t_parts = topic.split("/")
    for i, f in enumerate(f_parts):
        if f == "#":
            return True
        if i >= len(t_parts):
            return False
        if f != "+" and f != t_parts[i]:
            return False
    return len(f_parts) == len(t_parts)


class MQTTBroker(MessageBroker):
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        client_id_prefix: str,
        tls: bool = False,
        max_concurrency: int = 64,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        # unique per instance so multiple backend replicas can connect simultaneously
        self._client_id = f"{client_id_prefix}-{uuid.uuid4().hex[:8]}"
        self._tls = ssl.create_default_context() if tls else None
        self._subscriptions: list[tuple[str, MessageHandler, int]] = []
        self._client: aiomqtt.Client | None = None
        self._task: asyncio.Task | None = None
        self._connected = asyncio.Event()
        # bounded concurrency so a burst of events cannot exhaust the DB pool
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._inflight: set[asyncio.Task] = set()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def subscribe(self, topic_filter: str, handler: MessageHandler, qos: int = 1) -> None:
        self._subscriptions.append((topic_filter, handler, qos))

    async def publish(self, topic: str, payload: bytes, qos: int = 1, retain: bool = False) -> None:
        if not self._client or not self.connected:
            raise ConnectionError("MQTT broker not connected")
        await self._client.publish(topic, payload, qos=qos, retain=retain)

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="mqtt-consumer")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._inflight:
            await asyncio.gather(*self._inflight, return_exceptions=True)

    async def _run(self) -> None:
        backoff = 1
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self._host,
                    port=self._port,
                    username=self._username,
                    password=self._password,
                    identifier=self._client_id,
                    tls_context=self._tls,
                    protocol=aiomqtt.ProtocolVersion.V5,
                    keepalive=30,
                ) as client:
                    self._client = client
                    for topic_filter, _, qos in self._subscriptions:
                        await client.subscribe(topic_filter, qos=qos)
                    self._connected.set()
                    backoff = 1
                    logger.info(
                        "MQTT connected %s:%s as %s (%d subscriptions)",
                        self._host, self._port, self._client_id, len(self._subscriptions),
                    )
                    async for message in client.messages:
                        self._dispatch(str(message.topic), bytes(message.payload or b""))
            except asyncio.CancelledError:
                raise
            except aiomqtt.MqttError as exc:
                logger.warning("MQTT connection lost (%s); reconnecting in %ss", exc, backoff)
            except Exception:
                logger.exception("MQTT consumer crashed; reconnecting in %ss", backoff)
            finally:
                self._connected.clear()
                self._client = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def _dispatch(self, topic: str, payload: bytes) -> None:
        msg = IncomingMessage(topic=topic, payload=payload)
        for topic_filter, handler, _ in self._subscriptions:
            if topic_matches(topic_filter, topic):
                task = asyncio.create_task(self._guarded(handler, msg))
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)

    async def _guarded(self, handler: MessageHandler, msg: IncomingMessage) -> None:
        async with self._semaphore:
            try:
                await handler(msg)
            except Exception:
                logger.exception("handler failed for topic %s", msg.topic)
