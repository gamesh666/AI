"""Connection history written by the platform itself, stored as edge logs.

- system.connection  one record per outage of a device: status "offline" when it is lost, updated to
                     "recovered" (with the downtime) when the device is back. Same record, same event_id.
- system.platform    the platform's own start / stop, so outages of the central server are visible too.

They show up in the Edge Logs page (filter by type) and are pushed live like any other log.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge_device import EdgeDevice
from app.models.edge_log import EdgeLog
from app.realtime.broadcaster import broadcaster
from app.realtime.messages import RealtimeEventType
from app.repositories.edge_log_repository import EdgeLogRepository
from app.services.edge_log_service import log_to_read

logger = logging.getLogger(__name__)

CONNECTION = "system.connection"
PLATFORM = "system.platform"

# why a device was marked offline
REASON_HEARTBEAT_TIMEOUT = "heartbeat_timeout"
REASON_EDGE_REPORTED = "edge_reported_offline"  # MQTT Last Will or a graceful "offline"


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


class ConnectionHistory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EdgeLogRepository(session)

    async def _write(self, row: dict[str, Any], provided: set[str]) -> None:
        log, created = await self.repo.upsert(row, provided)
        await self.session.commit()
        await broadcaster.publish(
            RealtimeEventType.LOG_CREATED if created else RealtimeEventType.LOG_UPDATED,
            log_to_read(log).model_dump(mode="json"),
        )

    async def _open_record(self, device_id: uuid.UUID) -> EdgeLog | None:
        stmt = (
            select(EdgeLog)
            .where(EdgeLog.edge_device_id == device_id, EdgeLog.event_type == CONNECTION, EdgeLog.status == "offline")
            .order_by(EdgeLog.occurred_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def device_offline(self, device: EdgeDevice, reason: str, now: datetime | None = None) -> None:
        """Open an outage record (idempotent while one is already open)."""
        if await self._open_record(device.id) is not None:
            return
        now = now or datetime.now(UTC)
        # the connection was really lost around the last message we received
        lost_at = device.last_seen if reason == REASON_HEARTBEAT_TIMEOUT and device.last_seen else now
        row = {
            "id": uuid.uuid4(),
            "event_id": f"conn-{lost_at:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
            "edge_device_id": device.id,
            "camera_id": None,
            "camera_code": None,
            "event_type": CONNECTION,
            "severity": "warning",
            "status": "offline",
            "message": None,
            "data": {"offline_at": _iso(lost_at), "detected_at": _iso(now), "reason": reason,
                     "last_seen": _iso(device.last_seen)},
            "detections": [],
            "frame": None,
            "snapshot_key": None,
            "occurred_at": lost_at,
        }
        await self._write(row, set())
        logger.info("device %s offline (%s)", device.device_uuid, reason)

    async def device_online(self, device: EdgeDevice, now: datetime | None = None) -> None:
        """Close the open outage record, if any, with its duration."""
        record = await self._open_record(device.id)
        if record is None:
            return
        now = now or datetime.now(UTC)
        offline_at = record.occurred_at if record.occurred_at.tzinfo else record.occurred_at.replace(tzinfo=UTC)
        duration = max(0, int((now - offline_at).total_seconds()))
        row = {
            "id": uuid.uuid4(),
            "event_id": record.event_id,
            "edge_device_id": device.id,
            "event_type": CONNECTION,
            "severity": "info",
            "status": "recovered",
            "data": {"recovered_at": _iso(now), "duration_seconds": duration},
            "detections": [],
            "occurred_at": offline_at,
        }
        await self._write(row, {"severity", "status"})
        logger.info("device %s back online after %ds", device.device_uuid, duration)

    # ---- platform ---------------------------------------------------------------

    async def platform_started(self) -> None:
        now = datetime.now(UTC)
        last = (
            await self.session.execute(
                select(EdgeLog).where(EdgeLog.event_type == PLATFORM).order_by(EdgeLog.occurred_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        # best estimate of when the platform stopped: the newest thing it recorded
        last_activity = max(
            [t for t in (
                (await self.session.execute(select(func.max(EdgeDevice.last_seen)))).scalar_one_or_none(),
                (await self.session.execute(select(func.max(EdgeLog.updated_at)))).scalar_one_or_none(),
            ) if t is not None],
            default=None,
        )
        unclean = last is not None and last.status == "started"
        data: dict[str, Any] = {"started_at": _iso(now), "unclean_shutdown": unclean}
        if last is not None and last.status == "stopped":
            stopped_at = last.occurred_at
            data["stopped_at"] = _iso(stopped_at)
            data["downtime_seconds"] = max(0, int((now - stopped_at).total_seconds()))
        elif last_activity is not None:
            data["last_activity_at"] = _iso(last_activity)
            data["downtime_seconds"] = max(0, int((now - last_activity).total_seconds()))
        await self._write(self._platform_row("started", "warning" if unclean else "info", data, now), set())

    async def platform_stopped(self) -> None:
        now = datetime.now(UTC)
        await self._write(self._platform_row("stopped", "info", {"stopped_at": _iso(now)}, now), set())

    @staticmethod
    def _platform_row(status: str, severity: str, data: dict[str, Any], now: datetime) -> dict[str, Any]:
        return {
            "id": uuid.uuid4(),
            "event_id": f"platform-{status}-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
            "edge_device_id": None,
            "camera_id": None,
            "camera_code": None,
            "event_type": PLATFORM,
            "severity": severity,
            "status": status,
            "message": None,
            "data": data,
            "detections": [],
            "frame": None,
            "snapshot_key": None,
            "occurred_at": now,
        }
