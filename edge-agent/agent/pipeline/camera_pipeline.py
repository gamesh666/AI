"""Per-camera inference loop (runs entirely on the edge device).

    latest frame --(inference_fps)--> Detector --> confidence filter --> throttle
                 --> snapshot (JPEG, boxes drawn) -> MinIO (presigned PUT)
                 --> DetectionEvent -> MQTT edge/{device}/cameras/{camera}/events
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from agent.api_client.models import CameraConfig
from agent.camera.sources import FrameSource, SourceState
from agent.config import AgentSettings
from agent.inference.factory import create_detector
from agent.messaging.publisher import EdgePublisher
from agent.pipeline.event_builder import build_event
from agent.pipeline.throttle import EventThrottle
from agent.storage.snapshot_uploader import SnapshotUploader

logger = logging.getLogger(__name__)


@dataclass
class PipelineDeps:
    settings: AgentSettings
    publisher: EdgePublisher
    uploader: SnapshotUploader | None
    device_key: str


class CameraPipeline:
    def __init__(self, camera: CameraConfig, source: FrameSource, deps: PipelineDeps) -> None:
        self.camera = camera
        self._source = source
        self._deps = deps
        s = deps.settings
        self._detector = create_detector(s.detector, camera.ai_model, s.mock_detection_probability)
        self._model_name = camera.ai_model.name if camera.ai_model else self._detector.name
        self._throttle = EventThrottle(s.event_cooldown_seconds)
        self._interval = 1.0 / max(s.inference_fps, 0.1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"pipeline-{camera.stream_id}", daemon=True)
        self.error: str | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._detector.close()

    def _run(self) -> None:
        try:
            self._detector.load()
        except Exception as exc:
            self.error = f"detector load failed: {exc}"
            logger.error("[%s] %s", self.camera.name, self.error)
            return

        while not self._stop.is_set():
            started = time.monotonic()
            if self._source.state == SourceState.ONLINE:
                frame = self._source.latest()
                if frame is not None:
                    try:
                        self._process(frame)
                    except Exception:
                        logger.exception("[%s] pipeline iteration failed", self.camera.name)
            self._stop.wait(max(0.0, self._interval - (time.monotonic() - started)))

    def _process(self, frame) -> None:
        s = self._deps.settings
        detections = [d for d in self._detector.detect(frame) if d.confidence >= s.min_confidence]
        detections = [d for d in detections if self._throttle.allow(d.class_name)]
        if not detections:
            return

        snapshot_key = None
        if self._deps.uploader is not None:
            snapshot_key = self._deps.uploader.upload(self.camera.id, frame, detections)

        event = build_event(s.device_uuid, self.camera.id, self._model_name, detections, frame.shape, snapshot_key)
        self._deps.publisher.detection(event)
        logger.info("[%s] event %s: %s", self.camera.name, event.event_id,
                    ", ".join(f"{d.class_name}:{d.confidence:.2f}" for d in detections))
