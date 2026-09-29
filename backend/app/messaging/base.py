"""Broker abstraction.

Everything else in the backend depends on this interface only, so the MQTT broker (Mosquitto today,
EMQX tomorrow) or even the transport (e.g. Kafka) can be swapped by adding one implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    topic: str
    payload: bytes


MessageHandler = Callable[[IncomingMessage], Awaitable[None]]


class MessageBroker(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Connect and start consuming in the background (must auto-reconnect)."""

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def publish(self, topic: str, payload: bytes, qos: int = 1, retain: bool = False) -> None: ...

    @abstractmethod
    def subscribe(self, topic_filter: str, handler: MessageHandler, qos: int = 1) -> None:
        """Register a handler. Must be called before start()."""

    @property
    @abstractmethod
    def connected(self) -> bool: ...
