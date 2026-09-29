"""Suppresses repeated events: at most one event per (camera, class) every `cooldown` seconds."""

from __future__ import annotations

import time


class EventThrottle:
    def __init__(self, cooldown_seconds: float, clock=time.monotonic) -> None:
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        last = self._last.get(key)
        if last is not None and now - last < self._cooldown:
            return False
        self._last[key] = now
        return True
