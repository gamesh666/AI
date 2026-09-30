"""Camera capture: decode the camera stream and fan frames out to bounded queues.

The capture worker only decodes and enqueues — it never waits for inference, rendering or the
network, so AI latency cannot back-pressure the RTSP connection.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable

import cv2
import numpy as np

from agent.core.backoff import Backoff
from agent.core.frame_queue import BoundedFrameQueue, Frame
from agent.core.worker import Worker
from agent.monitoring.health import CameraHealth
from aivms_shared.payloads import RtspStatus

logger = logging.getLogger(__name__)

# RTSP over TCP inside OpenCV's FFmpeg backend (reliable across NAT/Wi-Fi); 5 s socket timeout
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|timeout;5000000")


class FrameSource(ABC):
    """Decoder abstraction (OpenCV/FFmpeg today; GStreamer / NVDEC later)."""

    @abstractmethod
    def open(self) -> None:
        """Raise on failure."""

    @abstractmethod
    def read(self) -> np.ndarray | None:
        """Next decoded BGR frame, or None when the stream broke."""

    @abstractmethod
    def close(self) -> None: ...


class RTSPSource(FrameSource):
    def __init__(self, url: str) -> None:
        self._url = url
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            raise ConnectionError("cannot open RTSP stream")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


SourceFactory = Callable[[str], FrameSource]

# scheme -> factory. Production ships RTSP; other sources (e.g. the simulation package's file / mock
# sources) are added at startup via agent.plugins, so production code never depends on them.
_SOURCES: dict[str, SourceFactory] = {"rtsp": RTSPSource, "rtsps": RTSPSource}


def register_source(scheme: str, factory: SourceFactory) -> None:
    _SOURCES[scheme.lower()] = factory


def supported_schemes() -> list[str]:
    return sorted(_SOURCES)


def create_source(url: str) -> FrameSource:
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    try:
        return _SOURCES[scheme](url)
    except KeyError:
        raise ValueError(f"unsupported camera source '{scheme}://' (supported: {', '.join(supported_schemes())})") \
            from None


class CaptureWorker(Worker):
    def __init__(self, camera_id: str, source: FrameSource, outputs: list[BoundedFrameQueue],
                 health: CameraHealth) -> None:
        super().__init__(f"capture-{camera_id}")
        self._source = source
        self._outputs = outputs
        self._health = health
        self._backoff = Backoff()
        self._opened = False
        self._seq = 0

    def step(self) -> None:
        if not self._opened:
            self._connect()
            return
        image = self._source.read()
        if image is None:
            self._source.close()
            self._opened = False
            self._health.rtsp_status = RtspStatus.OFFLINE
            self._health.set_error("rtsp", "stream read failed")
            delay = self._backoff.next_delay()
            logger.warning("[%s] camera stream lost; reconnect in %.0fs", self.name, delay)
            self.sleep(delay)
            return
        self._seq += 1
        frame = Frame(image=image, seq=self._seq)
        self._health.frame_captured(frame.width, frame.height)
        for queue in self._outputs:
            queue.put(frame)  # never blocks: oldest frame is dropped when full

    def _connect(self) -> None:
        self._health.rtsp_status = RtspStatus.CONNECTING
        try:
            self._source.open()
        except Exception as exc:
            self._health.rtsp_status = RtspStatus.OFFLINE
            self._health.set_error("rtsp", str(exc))
            delay = self._backoff.next_delay()
            logger.warning("[%s] camera connect failed (%s); retry in %.0fs", self.name, exc, delay)
            self.sleep(delay)
            return
        self._opened = True
        self._backoff.reset()
        self._health.rtsp_status = RtspStatus.ONLINE
        self._health.set_error("rtsp", None)
        logger.info("[%s] camera connected", self.name)

    def teardown(self) -> None:
        self._source.close()
        self._health.rtsp_status = RtspStatus.OFFLINE
