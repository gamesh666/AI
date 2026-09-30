"""One camera = one independent pipeline instance.

    CaptureWorker ──► inference_q (max 1) ──► InferenceWorker ──► DetectionStore ─┐
         │                                          └► DetectionProcessor ─► events_q ─► EventDispatcher
         └──────────► render_q (max 2) ──► RenderWorker (stream_fps, overlay) ◄───────┘
                                               └► publish_q (max 3) ──► PublishWorker ─► StreamPublisher
    (optional) PassthroughWorker: camera ──(-c copy)──► original/<site>/<device>/<camera>

Nothing is shared with other cameras. Every stage is a supervised Worker; a failing stage
backs off and retries without taking the rest of the pipeline down.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass

from agent.ai.detection_store import DetectionStore
from agent.ai.factory import DetectorOptions, create_detector
from agent.ai.inference_worker import InferenceWorker
from agent.ai.processor import DetectionProcessor, EventDispatcher, EventPolicy
from agent.ai.tracking import create_tracker
from agent.camera.capture import CaptureWorker, create_source
from agent.config.models import CameraConfig
from agent.config.settings import AgentSettings
from agent.core.frame_queue import BoundedFrameQueue
from agent.core.worker import Worker
from agent.messaging.publisher import EdgePublisher
from agent.monitoring.health import CameraHealth
from agent.storage.snapshot_uploader import SnapshotUploader
from agent.streaming.factory import PublishEndpoint, create_publisher
from agent.streaming.passthrough import PassthroughWorker
from agent.streaming.publish_worker import PublishWorker
from agent.video.encoder import EncoderSettings, create_encoder
from agent.video.overlay import OverlayRenderer
from agent.video.render_worker import RenderWorker
from aivms_shared.payloads import AiStatus, CameraRuntimeStatus, StreamStatus

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Shared, thread-safe services handed to every pipeline."""

    settings: AgentSettings
    device_id: str
    publisher: EdgePublisher  # MQTT
    uploader: SnapshotUploader | None
    endpoint: PublishEndpoint  # media server push endpoint


class CameraPipeline:
    def __init__(self, camera: CameraConfig, ctx: PipelineContext) -> None:
        self.camera = camera
        s = ctx.settings
        cid = camera.camera_id
        stream_on = camera.stream_enabled and camera.annotated_stream_enabled
        self.health = CameraHealth(cid, ai_enabled=camera.ai_enabled, stream_enabled=stream_on)
        self.workers: list[Worker] = []

        overlay = OverlayRenderer()
        inference_q = BoundedFrameQueue(s.inference_queue_size, f"{cid}-inference")
        render_q = BoundedFrameQueue(s.render_queue_size, f"{cid}-render")
        publish_q = BoundedFrameQueue(s.publish_queue_size, f"{cid}-publish")
        capture_outputs = []

        # ---- AI branch ----
        store = tracker = None
        if camera.ai_enabled:
            capture_outputs.append(inference_q)
            store = DetectionStore()
            tracker = create_tracker(s.tracker)
            events: queue.Queue = queue.Queue(maxsize=s.event_queue_size)
            model_name = camera.ai_model.name if camera.ai_model else s.detector
            processor = DetectionProcessor(s.min_confidence, EventPolicy(s.event_cooldown_seconds), events)
            detector = create_detector(s.detector, camera,
                                       DetectorOptions(device=s.detector_device, conf=min(s.min_confidence, 0.25)),
                                       fallback=s.detector_fallback)
            self.workers.append(InferenceWorker(cid, inference_q, detector, tracker, store, processor, self.health,
                                                camera.video.inference_fps))
            self.workers.append(EventDispatcher(cid, camera.id, ctx.device_id, model_name, events, ctx.publisher,
                                                ctx.uploader, overlay))

        # ---- annotated video branch ----
        if stream_on:
            capture_outputs.append(render_q)
            v = camera.video
            encoder_settings = EncoderSettings(width=v.width or 0, height=v.height or 0, fps=v.stream_fps,
                                               codec=v.video_codec, bitrate=v.bitrate, gop_size=v.gop_size,
                                               encoder=s.video_encoder)
            stream_publisher = create_publisher(ctx.endpoint, camera.stream_path, encoder_settings,
                                                lambda es: create_encoder(es, s.ffmpeg_path))
            self.workers.append(RenderWorker(cid, render_q, publish_q, overlay, store, None, v.stream_fps,
                                             v.width, v.height, s.detection_hold_seconds, hud_text=camera.name))
            self.workers.append(PublishWorker(cid, publish_q, stream_publisher, self.health))

        # ---- capture (first in the chain, started last) ----
        self.workers.insert(0, CaptureWorker(cid, create_source(camera.rtsp_url), capture_outputs, self.health))
        self.health.track_drops(inference_q, render_q, publish_q)

        # ---- optional original passthrough ----
        is_rtsp = camera.rtsp_url.startswith(("rtsp://", "rtsps://"))
        if camera.stream_enabled and camera.original_stream_enabled and is_rtsp:
            self.workers.append(PassthroughWorker(cid, camera.rtsp_url, ctx.endpoint, camera.original_stream_path,
                                                  s.ffmpeg_path))

    def start(self) -> None:
        logger.info("starting pipeline %s (%s) ai=%s stream=%s path=%s", self.camera.camera_id, self.camera.name,
                    self.camera.ai_enabled, self.camera.stream_enabled, self.camera.stream_path)
        for worker in reversed(self.workers):  # consumers before the producer
            worker.start()

    def stop(self) -> None:
        logger.info("stopping pipeline %s", self.camera.camera_id)
        for worker in self.workers:
            worker.stop()
        self.health.stream_status = StreamStatus.OFFLINE
        if self.camera.ai_enabled:
            self.health.ai_status = AiStatus.DISABLED

    def supervise(self) -> None:
        """Restart any worker thread that died unexpectedly."""
        for worker in self.workers:
            if not worker.stopped and not worker.is_alive():
                logger.warning("worker %s died; restarting", worker.name)
                worker.start()

    def status(self) -> CameraRuntimeStatus:
        return self.health.snapshot()
