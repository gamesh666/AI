"""Keeps one independent CameraPipeline per enabled camera, in sync with the server configuration."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from agent.camera.pipeline import CameraPipeline, PipelineContext
from agent.config.models import CameraConfig
from aivms_shared.payloads import CameraRuntimeStatus

logger = logging.getLogger(__name__)

PipelineFactory = Callable[[CameraConfig, PipelineContext], CameraPipeline]


class CameraManager:
    def __init__(self, ctx: PipelineContext, factory: PipelineFactory = CameraPipeline) -> None:
        self._ctx = ctx
        self._factory = factory
        self._pipelines: dict[str, CameraPipeline] = {}
        self._lock = threading.Lock()

    def set_endpoint(self, endpoint) -> None:
        """Media server endpoint for pipelines started from now on."""
        self._ctx.endpoint = endpoint

    def apply(self, cameras: list[CameraConfig]) -> None:
        """Diff by config fingerprint: only added/changed/removed cameras are (re)started."""
        desired = {c.camera_id: c for c in cameras if c.enabled and c.rtsp_url}
        for c in cameras:
            if c.enabled and not c.rtsp_url:
                logger.info("camera %s: source managed outside this agent; skipped", c.camera_id)
        with self._lock:
            for cam_id in list(self._pipelines):
                pipeline = self._pipelines[cam_id]
                if cam_id not in desired or pipeline.camera.fingerprint() != desired[cam_id].fingerprint():
                    self._stop(cam_id)
            for cam_id, cam in desired.items():
                if cam_id not in self._pipelines:
                    self._start(cam)
        logger.info("camera set applied: %d pipeline(s) running", len(self._pipelines))

    def restart(self, camera_id: str) -> bool:
        with self._lock:
            pipeline = self._pipelines.get(camera_id)
            if pipeline is None:
                return False
            self._stop(camera_id)
            self._start(pipeline.camera)
        return True

    def supervise(self) -> None:
        with self._lock:
            pipelines = list(self._pipelines.values())
        for pipeline in pipelines:
            try:
                pipeline.supervise()
            except Exception:
                logger.exception("supervising %s failed", pipeline.camera.camera_id)

    def statuses(self) -> list[CameraRuntimeStatus]:
        with self._lock:
            pipelines = list(self._pipelines.values())
        return [p.status() for p in pipelines]

    def camera_ids(self) -> list[str]:
        with self._lock:
            return list(self._pipelines)

    def stop_all(self) -> None:
        with self._lock:
            for cam_id in list(self._pipelines):
                self._stop(cam_id)

    # ---- internals (caller holds the lock) ----------------------------------------

    def _start(self, camera: CameraConfig) -> None:
        try:
            pipeline = self._factory(camera, self._ctx)
            pipeline.start()
        except Exception:
            # a broken camera config must not prevent the other cameras from running
            logger.exception("failed to start pipeline for %s", camera.camera_id)
            return
        self._pipelines[camera.camera_id] = pipeline

    def _stop(self, camera_id: str) -> None:
        pipeline = self._pipelines.pop(camera_id, None)
        if pipeline is None:
            return
        try:
            pipeline.stop()
        except Exception:
            logger.exception("failed to stop pipeline for %s", camera_id)
