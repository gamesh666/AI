"""Reconnect backoff: 1 s, 2 s, 5 s, 10 s, 30 s, 30 s, … (maximum 30 s)."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

DEFAULT_SCHEDULE: tuple[float, ...] = (1, 2, 5, 10, 30)


class Backoff:
    def __init__(self, schedule: Sequence[float] = DEFAULT_SCHEDULE, clock: Callable[[], float] = time.monotonic):
        self._schedule = tuple(schedule)
        self._clock = clock
        self._attempt = 0
        self._next_at = 0.0

    @property
    def attempts(self) -> int:
        return self._attempt

    def next_delay(self) -> float:
        """Delay to wait before the next attempt; advances the schedule."""
        delay = self._schedule[min(self._attempt, len(self._schedule) - 1)]
        self._attempt += 1
        self._next_at = self._clock() + delay
        return delay

    def ready(self) -> bool:
        """Non-blocking variant: True when the current delay has elapsed."""
        return self._clock() >= self._next_at

    def reset(self) -> None:
        self._attempt = 0
        self._next_at = 0.0
