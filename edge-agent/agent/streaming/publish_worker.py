"""Publish worker: takes annotated frames and hands them to the StreamPublisher.

Runs in its own thread so a slow or broken network only affects this stage: capture and
inference keep running (and detection events keep flowing) while the publisher reconnects.
"""

from __future__ import annotations

from agent.core.frame_queue import BoundedFrameQueue
from agent.core.worker import Worker
from agent.monitoring.health import CameraHealth
from agent.streaming.publisher import StreamPublisher
from aivms_shared.payloads import StreamStatus


class PublishWorker(Worker):
    def __init__(self, camera_id: str, source: BoundedFrameQueue, publisher: StreamPublisher,
                 health: CameraHealth) -> None:
        super().__init__(f"publish-{camera_id}")
        self._source = source
        self._publisher = publisher
        self._health = health

    def step(self) -> None:
        frame = self._source.get(timeout=1.0)
        if frame is not None and self._publisher.publish(frame.image):
            self._health.output.tick()
        self._health.stream_status = self._publisher.status
        self._health.set_error("stream", self._publisher.last_error
                               if self._publisher.status != StreamStatus.STREAMING else None)

    def on_stop(self) -> None:
        self._publisher.stop()

    def teardown(self) -> None:
        self._publisher.stop()
        self._health.stream_status = StreamStatus.OFFLINE
