"""Publishes a heartbeat every `interval` seconds (default 10s)."""

from __future__ import annotations

import logging
import threading

from agent import __version__
from agent.messaging.publisher import EdgePublisher
from agent.telemetry.system_metrics import SystemMetrics
from aivms_shared.payloads import Heartbeat

logger = logging.getLogger(__name__)


class HeartbeatReporter:
    def __init__(self, device_uuid: str, publisher: EdgePublisher, metrics: SystemMetrics, interval: float) -> None:
        self._device = device_uuid
        self._publisher = publisher
        self._metrics = metrics
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)

    def build(self) -> Heartbeat:
        gpu = self._metrics.gpu()
        return Heartbeat(
            device_uuid=self._device,
            cpu_usage=self._metrics.cpu_usage(),
            memory_usage=self._metrics.memory_usage(),
            gpu_usage=gpu.usage,
            gpu_memory_usage=gpu.memory_usage,
            temperature=gpu.temperature if gpu.temperature is not None else self._metrics.cpu_temperature(),
            agent_version=__version__,
            hostname=self._metrics.hostname(),
            ip_address=self._metrics.primary_ip(),
            gpu_name=gpu.name,
            gpu_memory=gpu.total_memory_mb,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._publisher.heartbeat(self.build())
            except Exception:
                logger.exception("heartbeat failed")
            self._stop.wait(self.interval)
