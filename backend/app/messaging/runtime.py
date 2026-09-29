"""Process-wide broker handle (kept import-free to avoid cycles)."""

from __future__ import annotations

from app.messaging.base import MessageBroker

_broker: MessageBroker | None = None


def set_broker(broker: MessageBroker | None) -> None:
    global _broker
    _broker = broker


def get_broker() -> MessageBroker | None:
    return _broker
