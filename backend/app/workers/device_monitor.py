"""Marks devices offline when heartbeats stop.

Runs in every backend replica, but a Redis lock guarantees only one replica
does the work per interval.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import get_session_factory
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)

LOCK_KEY = "aivms:lock:device-monitor"


class DeviceMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def _tick(self, interval: int) -> None:
        acquired = await get_redis().set(LOCK_KEY, "1", nx=True, ex=max(interval - 1, 1))
        if not acquired:
            return
        async with get_session_factory()() as session:
            changed = await DeviceService(session).mark_stale_offline()
        if changed:
            logger.info("marked %d device(s) offline", changed)

    async def _run(self) -> None:
        settings = get_settings()
        interval = settings.device_monitor_interval_seconds
        # after a platform restart every device looks stale until its next heartbeat: give them time
        # to report in, so the platform's own downtime is not recorded as an outage of every device
        await asyncio.sleep(settings.device_offline_after_seconds)
        while True:
            try:
                await self._tick(interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("device monitor tick failed")
            await asyncio.sleep(interval)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="device-monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
