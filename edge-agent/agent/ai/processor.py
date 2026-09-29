"""Detection processing: decide which detections become events, then dispatch them asynchronously.

    InferenceWorker ─► DetectionProcessor.process()  (filter + event decision, cheap, in-thread)
                          └► bounded event queue (drop when full)
                               └► EventDispatcher worker: annotated JPEG snapshot → MinIO,
                                  DetectionEvent → MQTT edge/{device}/cameras/{camera}/events

Snapshot upload and MQTT publishing never slow down inference.
"""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass

from agent.ai.detector import Detection
from agent.core.frame_queue import Frame
from agent.core.worker import Worker
from agent.messaging.publisher import EdgePublisher
from agent.storage.snapshot_uploader import SnapshotUploader
from agent.video.overlay import OverlayRenderer
from aivms_shared.payloads import BBox, DetectionEvent, FrameInfo
from aivms_shared.payloads import Detection as DetectionPayload

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EventJob:
    frame: Frame
    detections: list[Detection]  # all detections of the frame (for the snapshot)
    triggers: list[Detection]  # the ones that caused the event (sent as metadata)


class EventPolicy:
    """New track → event. Without tracking: at most one event per class every `cooldown` seconds."""

    def __init__(self, cooldown_seconds: float, clock=time.monotonic, max_tracks: int = 10_000) -> None:
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._seen_tracks: dict[int, float] = {}
        self._max_tracks = max_tracks
        self._last_by_class: dict[str, float] = {}

    def triggers(self, detections: list[Detection]) -> list[Detection]:
        now = self._clock()
        out = []
        for det in detections:
            if det.track_id is not None:
                if det.track_id not in self._seen_tracks:
                    out.append(det)
                self._seen_tracks[det.track_id] = now
            else:
                last = self._last_by_class.get(det.class_name)
                if last is None or now - last >= self._cooldown:
                    self._last_by_class[det.class_name] = now
                    out.append(det)
        if len(self._seen_tracks) > self._max_tracks:  # bounded memory
            cutoff = sorted(self._seen_tracks.values())[len(self._seen_tracks) // 2]
            self._seen_tracks = {k: v for k, v in self._seen_tracks.items() if v >= cutoff}
        return out


class DetectionProcessor:
    def __init__(self, min_confidence: float, policy: EventPolicy, events: queue.Queue) -> None:
        self._min_confidence = min_confidence
        self._policy = policy
        self._events = events
        self.dropped_events = 0

    def process(self, frame: Frame, detections: list[Detection]) -> None:
        confident = [d for d in detections if d.confidence >= self._min_confidence]
        triggers = self._policy.triggers(confident)
        if not triggers:
            return
        try:
            self._events.put_nowait(EventJob(frame, confident, triggers))
        except queue.Full:
            self.dropped_events += 1
            logger.warning("event queue full; event dropped (%d so far)", self.dropped_events)


def to_payload(device_id: str, camera_id: str, model_name: str, job: EventJob,
               snapshot_key: str | None) -> DetectionEvent:
    return DetectionEvent(
        device_id=device_id,
        camera_id=camera_id,
        model=model_name,
        frame=FrameInfo(width=job.frame.width, height=job.frame.height),
        snapshot_key=snapshot_key,
        detections=[
            DetectionPayload(
                track_id=d.track_id,
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                bbox=BBox(x1=d.bbox.x1, y1=d.bbox.y1, x2=d.bbox.x2, y2=d.bbox.y2),
                attributes=d.attributes,
            )
            for d in job.triggers
        ],
    )


class EventDispatcher(Worker):
    def __init__(self, camera_id: str, camera_uuid: str, device_id: str, model_name: str,
                 events: queue.Queue, publisher: EdgePublisher, uploader: SnapshotUploader | None,
                 overlay: OverlayRenderer) -> None:
        super().__init__(f"events-{camera_id}")
        self._camera_id = camera_id
        self._camera_uuid = camera_uuid
        self._device_id = device_id
        self._model_name = model_name
        self._events = events
        self._publisher = publisher
        self._uploader = uploader
        self._overlay = overlay

    def step(self) -> None:
        try:
            job: EventJob = self._events.get(timeout=1.0)
        except queue.Empty:
            return
        snapshot_key = None
        if self._uploader is not None:
            annotated = self._overlay.draw(job.frame.image.copy(), job.detections)
            snapshot_key = self._uploader.upload(self._camera_uuid, annotated)
        event = to_payload(self._device_id, self._camera_id, self._model_name, job, snapshot_key)
        self._publisher.detection(event)  # MQTT QoS1; queued by paho while offline
        logger.info("[%s] event %s: %s", self.name, event.event_id,
                    ", ".join(f"{d.class_name}#{d.track_id}:{d.confidence:.2f}" for d in event.detections))
