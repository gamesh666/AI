"""Telemetry over HTTPS with the device key: the alternative to the shared MQTT account.

Same payloads as MQTT, POSTed to /edge/heartbeat, /edge/status, /edge/cameras/{id}/status and /edge/events.
A background thread sends them so camera pipelines never wait on the network. What MQTT pushes to the edge
(commands, config changes) comes back in the heartbeat answer and is handed to `on_heartbeat_ack`.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from agent.api_client.client import ApiError, BackendClient
from aivms_shared.payloads import CameraRuntimeStatus, DetectionEvent, DeviceStatus, Heartbeat

logger = logging.getLogger(__name__)

HeartbeatAck = Callable[[dict], None]


@dataclass(slots=True)
class _Item:
    path: str
    body: bytes
    # events are worth retrying; heartbeat / status are periodic and simply superseded by the next one
    retries_left: int = 0
    is_heartbeat: bool = False


class HttpPublisher:
    RETRY_DELAY_SECONDS = 2.0

    def __init__(self, api: BackendClient, on_heartbeat_ack: HeartbeatAck | None = None,
                 max_queued: int = 5000, event_retries: int = 30) -> None:
        self._api = api
        self._on_ack = on_heartbeat_ack
        self._event_retries = event_retries
        self._queue: queue.Queue[_Item] = queue.Queue(maxsize=max_queued)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="http-telemetry", daemon=True)

    @property
    def ready(self) -> bool:
        return True  # queued until the platform is reachable

    def configure_last_will(self) -> None:
        """No Last Will over HTTP: the platform marks the device offline when heartbeats stop."""

    def heartbeat(self, hb: Heartbeat) -> None:
        self._put(_Item("/edge/heartbeat", hb.to_bytes(), is_heartbeat=True))

    def status(self, status: DeviceStatus) -> None:
        self._put(_Item("/edge/status", status.to_bytes()))

    def camera_status(self, status: CameraRuntimeStatus) -> None:
        self._put(_Item(f"/edge/cameras/{status.camera_id}/status", status.to_bytes()))

    def detection(self, event: DetectionEvent) -> None:
        self._put(_Item("/edge/events", event.to_bytes(), retries_left=self._event_retries))

    def start(self) -> None:
        self._thread.start()

    def stop(self, flush_seconds: float = 3.0) -> None:
        """Stops after trying to send what is queued (e.g. the final "offline" status) for a few seconds."""
        self._stop.set()
        self._thread.join(flush_seconds)

    def _put(self, item: _Item) -> None:
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()  # drop the oldest: fresh telemetry matters more
            except queue.Empty:
                pass
            self._queue.put_nowait(item)
            logger.warning("telemetry queue full; dropped the oldest message")

    def _send(self, item: _Item) -> bool:
        """True when done with the item (sent or refused), False to retry it later."""
        try:
            answer = self._api.post_telemetry(item.path, item.body)
        except ApiError as exc:
            if exc.status_code is not None and exc.status_code < 500:
                logger.warning("platform refused %s: %s", item.path, exc)
                return True
            logger.warning("sending %s failed: %s", item.path, exc)
            return item.retries_left <= 0
        if item.is_heartbeat and self._on_ack and answer:
            try:
                self._on_ack(answer)
            except Exception:
                logger.exception("heartbeat answer handling failed")
        return True

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                if self._stop.is_set():
                    return
                continue
            if self._send(item):
                continue
            item.retries_left -= 1
            self._put(item)
            if self._stop.wait(self.RETRY_DELAY_SECONDS):
                return
