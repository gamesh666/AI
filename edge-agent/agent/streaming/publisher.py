"""StreamPublisher: pushes encoded video from the edge to the central media server.

All connections are OUTGOING from the edge (NAT / firewall friendly). The central server never
connects to an edge device or a camera.

    StreamPublisher (interface: connect / publish / reconnect / stop)
     └─ EncoderPublisher (VideoEncoder + reconnect with backoff)
         ├─ RTSPPublisher   RTSP over TCP push   (LAN / VPN)          — MVP
         ├─ SRTPublisher    SRT push             (across the Internet) — MVP, reserved as default for WAN
         └─ WebRTCPublisher WHIP push            (future)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np

from agent.core.backoff import Backoff
from agent.video.encoder import EncoderError, EncoderSettings, VideoEncoder
from aivms_shared.payloads import StreamStatus

logger = logging.getLogger(__name__)


class StreamPublisher(ABC):
    status: StreamStatus = StreamStatus.OFFLINE
    last_error: str | None = None

    @abstractmethod
    def connect(self, width: int, height: int) -> None:
        """Open the outgoing connection for frames of this size. Raises on failure."""

    @abstractmethod
    def publish(self, frame: np.ndarray) -> bool:
        """Send one frame. Never raises and never blocks on reconnection: returns False if dropped."""

    @abstractmethod
    def reconnect(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


EncoderFactory = Callable[[EncoderSettings], VideoEncoder]


class EncoderPublisher(StreamPublisher):
    """Publisher backed by a VideoEncoder process writing to `target_url`."""

    output_format = "rtsp"

    def __init__(self, target_url: str, display_url: str, settings: EncoderSettings,
                 encoder_factory: EncoderFactory, backoff: Backoff | None = None,
                 settle_seconds: float = 2.0, clock=time.monotonic) -> None:
        self._target = target_url  # contains credentials — never log it
        self.display_url = display_url
        self._settings = settings
        self._factory = encoder_factory
        self._encoder: VideoEncoder | None = None
        self._backoff = backoff or Backoff()
        # an encoder process accepts frames before its outgoing connection is established; only
        # after it has stayed up this long is the stream considered live (and the backoff reset)
        self._settle = settle_seconds
        self._clock = clock
        self._connected_at = 0.0
        self.status = StreamStatus.CONNECTING

    def output_args(self) -> list[str]:
        return []

    def connect(self, width: int, height: int) -> None:
        self._close_encoder()
        settings = EncoderSettings(width=width, height=height, fps=self._settings.fps, codec=self._settings.codec,
                                   bitrate=self._settings.bitrate, gop_size=self._settings.gop_size,
                                   encoder=self._settings.encoder)
        self.status = StreamStatus.CONNECTING
        encoder = self._factory(settings)
        encoder.start(self._target, self.output_format, self.output_args())
        self._encoder = encoder
        self._connected_at = self._clock()
        logger.info("connecting %s", self.display_url)

    def publish(self, frame: np.ndarray) -> bool:
        h, w = frame.shape[:2]
        enc = self._encoder
        if enc is not None and not enc.alive:
            # the encoder/connection died on its own (server down, auth refused, network lost)
            detail = enc.error_detail() if hasattr(enc, "error_detail") else ""
            self._failed(f"encoder exited{': ' + detail if detail else ''}")
            return False
        if enc is None or (getattr(enc, "settings", None) and (enc.settings.width, enc.settings.height) != (w, h)):
            if not self._backoff.ready():
                return False  # waiting for the next reconnect attempt: drop, keep the pipeline moving
            try:
                self.connect(w, h)
            except Exception as exc:
                self._failed(f"connect failed: {exc}")
                return False
            enc = self._encoder
        try:
            enc.write(frame)
        except EncoderError as exc:
            self._failed(str(exc))
            return False
        if self.status != StreamStatus.STREAMING and self._clock() - self._connected_at >= self._settle:
            self.status = StreamStatus.STREAMING
            self.last_error = None
            self._backoff.reset()
            logger.info("streaming %s", self.display_url)
        return True

    def reconnect(self) -> None:
        self._close_encoder()
        self._backoff.reset()
        self.status = StreamStatus.CONNECTING

    def stop(self) -> None:
        self._close_encoder()
        self.status = StreamStatus.OFFLINE

    def _failed(self, reason: str) -> None:
        self._close_encoder()
        self.status = StreamStatus.ERROR
        self.last_error = reason
        delay = self._backoff.next_delay()
        logger.warning("publish %s failed (%s); reconnect in %.0fs", self.display_url, reason, delay)

    def _close_encoder(self) -> None:
        enc, self._encoder = self._encoder, None
        if enc is not None:
            try:
                enc.close()
            except Exception:
                logger.debug("encoder close failed", exc_info=True)
