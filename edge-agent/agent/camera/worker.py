"""One camera = frame source + (optional) inference pipeline + (optional) stream relay."""

from __future__ import annotations

import logging

from agent.api_client.models import CameraConfig
from agent.camera.sources import FrameSource, SourceState, create_source
from agent.camera.stream_relay import FFmpegRelay, build_publish_url
from agent.pipeline.camera_pipeline import CameraPipeline, PipelineDeps
from aivms_shared.payloads import CameraState, CameraStatus

logger = logging.getLogger(__name__)


class CameraWorker:
    def __init__(self, camera: CameraConfig, deps: PipelineDeps, relay_base_url: str | None) -> None:
        self.camera = camera
        self.source: FrameSource = create_source(camera.rtsp_url)
        self.pipeline: CameraPipeline | None = None
        self.relay: FFmpegRelay | None = None

        if camera.ai_enabled:
            self.pipeline = CameraPipeline(camera, self.source, deps)

        s = deps.settings
        if relay_base_url and s.stream_relay_enabled:
            if FFmpegRelay.available(s.ffmpeg_path):
                publish = build_publish_url(relay_base_url, camera.stream_id, s.device_uuid, deps.device_key)
                self.relay = FFmpegRelay(s.ffmpeg_path, camera.rtsp_url, publish, camera.stream_id)
            else:
                logger.warning("ffmpeg not found; live stream relay disabled for %s", camera.name)

    def start(self) -> None:
        logger.info("starting camera %s (%s)", self.camera.name, self.camera.stream_id)
        self.source.start()
        if self.relay:
            self.relay.start()
        if self.pipeline:
            self.pipeline.start()

    def stop(self) -> None:
        logger.info("stopping camera %s", self.camera.name)
        if self.pipeline:
            self.pipeline.stop()
        if self.relay:
            self.relay.stop()
        self.source.stop()

    def status(self) -> CameraStatus:
        mapping = {
            SourceState.ONLINE: CameraState.ONLINE,
            SourceState.ERROR: CameraState.ERROR,
        }
        state = mapping.get(self.source.state, CameraState.OFFLINE)
        error = self.source.error
        if self.pipeline and self.pipeline.error:
            state, error = CameraState.ERROR, self.pipeline.error
        return CameraStatus(camera_id=self.camera.id, state=state, fps=self.source.fps or None, error=error)
