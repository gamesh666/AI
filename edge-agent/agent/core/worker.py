"""Supervised worker thread.

A worker runs `step()` in a loop. An exception in one step is logged and the loop continues after a
backoff; it never propagates, so one failing stage cannot crash its camera pipeline — let alone the
other cameras on the same edge device.
"""

from __future__ import annotations

import logging
import threading

from agent.core.backoff import Backoff

logger = logging.getLogger(__name__)


class Worker:
    name = "worker"

    def __init__(self, name: str | None = None) -> None:
        if name:
            self.name = name
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error_backoff = Backoff()
        self.last_error: str | None = None

    # ---- lifecycle -------------------------------------------------------------

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self.on_stop()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def sleep(self, seconds: float) -> bool:
        """Interruptible sleep; returns True if the worker is stopping."""
        return self._stop.wait(max(0.0, seconds))

    # ---- hooks -----------------------------------------------------------------

    def setup(self) -> None:
        """Called once in the worker thread before the loop."""

    def step(self) -> None:
        raise NotImplementedError

    def on_stop(self) -> None:
        """Called from stop() (any thread) — release blocking resources here."""

    def teardown(self) -> None:
        """Called in the worker thread after the loop."""

    # ---- loop ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self.setup()
            while not self._stop.is_set():
                try:
                    self.step()
                    self._error_backoff.reset()
                except Exception as exc:  # isolate failures: log, back off, continue
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    delay = self._error_backoff.next_delay()
                    logger.exception("[%s] step failed; retry in %.0fs", self.name, delay)
                    self.sleep(delay)
        except Exception:
            logger.exception("[%s] crashed", self.name)
        finally:
            try:
                self.teardown()
            except Exception:
                logger.exception("[%s] teardown failed", self.name)
