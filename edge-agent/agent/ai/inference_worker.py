"""Inference worker: runs the detector at `inference_fps` on the NEWEST captured frame.

Decoupled from capture and streaming: if the model is slow, older frames are simply dropped.
"""

from __future__ import annotations

import logging
import time

from agent.ai.detection_store import DetectionResult, DetectionStore
from agent.ai.detector import Detector
from agent.ai.processor import DetectionProcessor
from agent.ai.tracking import Tracker
from agent.core.frame_queue import BoundedFrameQueue
from agent.core.worker import Worker
from agent.monitoring.health import CameraHealth
from aivms_shared.payloads import AiStatus

logger = logging.getLogger(__name__)


class InferenceWorker(Worker):
    def __init__(self, camera_id: str, source: BoundedFrameQueue, detector: Detector, tracker: Tracker,
                 store: DetectionStore, processor: DetectionProcessor, health: CameraHealth,
                 inference_fps: float) -> None:
        super().__init__(f"inference-{camera_id}")
        self._source = source
        self._detector = detector
        self._tracker = tracker
        self._store = store
        self._processor = processor
        self._health = health
        self._interval = 1.0 / max(inference_fps, 0.1)
        self._loaded = False

    def step(self) -> None:
        if not self._loaded:
            self._load()
        frame = self._source.get_latest(timeout=1.0)
        if frame is None:
            return
        started = time.monotonic()
        detections = self._detector.detect(frame)
        detections = self._tracker.update(detections, frame.monotonic)
        self._store.set(DetectionResult(detections, frame.width, frame.height, frame.monotonic))
        self._health.inference.tick()
        self._health.ai_status = AiStatus.RUNNING
        self._health.set_error("ai", None)
        self._processor.process(frame, detections)
        # pace to inference_fps; frames captured meanwhile are dropped by the bounded queue
        self.sleep(self._interval - (time.monotonic() - started))

    def _load(self) -> None:
        self._health.ai_status = AiStatus.LOADING
        try:
            self._detector.load()
        except Exception as exc:
            self._health.ai_status = AiStatus.ERROR
            self._health.set_error("ai", f"model load failed: {exc}")
            raise  # Worker backs off and retries; capture and streaming keep running
        self._loaded = True
        self._health.ai_status = AiStatus.RUNNING
        logger.info("[%s] detector '%s' ready", self.name, self._detector.name)

    def teardown(self) -> None:
        self._detector.close()
