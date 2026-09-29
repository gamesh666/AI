"""Keeps the running camera workers in sync with the configuration served by the backend."""

from __future__ import annotations

import logging
import threading

from agent.api_client.models import CameraConfig
from agent.camera.worker import CameraWorker
from agent.pipeline.camera_pipeline import PipelineDeps
from aivms_shared.payloads import CameraStatus

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, deps: PipelineDeps) -> None:
        self._deps = deps
        self._workers: dict[str, CameraWorker] = {}
        self._lock = threading.Lock()

    def apply(self, cameras: list[CameraConfig], relay_base_url: str | None) -> None:
        desired = {c.id: c for c in cameras if c.enabled}
        with self._lock:
            for cam_id in list(self._workers):
                worker = self._workers[cam_id]
                if cam_id not in desired or worker.camera.fingerprint() != desired[cam_id].fingerprint():
                    worker.stop()
                    del self._workers[cam_id]
            for cam_id, cam in desired.items():
                if cam_id not in self._workers:
                    worker = CameraWorker(cam, self._deps, relay_base_url)
                    worker.start()
                    self._workers[cam_id] = worker
        logger.info("camera set applied: %d running", len(self._workers))

    def restart(self, camera_id: str, relay_base_url: str | None) -> bool:
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker is None:
            return False
        worker.stop()
        with self._lock:
            new = CameraWorker(worker.camera, self._deps, relay_base_url)
            new.start()
            self._workers[camera_id] = new
        return True

    def statuses(self) -> list[CameraStatus]:
        with self._lock:
            return [w.status() for w in self._workers.values()]

    def worker(self, camera_id: str) -> CameraWorker | None:
        return self._workers.get(camera_id)

    def stop_all(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.stop()
            self._workers.clear()
