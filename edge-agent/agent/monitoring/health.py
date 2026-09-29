"""Per-camera health: RTSP input, AI, stream output — reported to edge/{device}/cameras/{camera}/status."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import UTC, datetime

from aivms_shared.payloads import AiStatus, CameraRuntimeStatus, RtspStatus, StreamStatus


class FpsMeter:
    """Frames per second over a sliding window (thread-safe)."""

    def __init__(self, window_seconds: float = 5.0, clock=time.monotonic) -> None:
        self._window = window_seconds
        self._clock = clock
        self._ticks: deque[float] = deque()
        self._started: float | None = None
        self._lock = threading.Lock()

    def tick(self) -> None:
        now = self._clock()
        with self._lock:
            if self._started is None:
                self._started = now
            self._ticks.append(now)
            self._trim(now)

    def fps(self) -> float:
        """Ticks in the window / window length (shorter while the meter is young); decays to 0 on stall."""
        now = self._clock()
        with self._lock:
            self._trim(now)
            if self._started is None:
                return 0.0
            elapsed = min(self._window, now - self._started)
            return round(len(self._ticks) / elapsed, 1) if elapsed > 0 else 0.0

    def _trim(self, now: float) -> None:
        while self._ticks and now - self._ticks[0] > self._window:
            self._ticks.popleft()


class CameraHealth:
    def __init__(self, camera_id: str, ai_enabled: bool, stream_enabled: bool) -> None:
        self.camera_id = camera_id
        self.rtsp_status = RtspStatus.CONNECTING
        self.ai_status = AiStatus.LOADING if ai_enabled else AiStatus.DISABLED
        self.stream_status = StreamStatus.CONNECTING if stream_enabled else StreamStatus.OFFLINE
        self.input = FpsMeter()
        self.inference = FpsMeter()
        self.output = FpsMeter()
        self.resolution: str | None = None
        self.last_frame_at: datetime | None = None
        self._errors: dict[str, str] = {}
        self._dropped_sources: list = []
        self._lock = threading.Lock()

    # ---- updates from workers ---------------------------------------------------

    def frame_captured(self, width: int, height: int) -> None:
        self.input.tick()
        self.last_frame_at = datetime.now(UTC)
        self.resolution = f"{width}x{height}"

    def set_error(self, stage: str, message: str | None) -> None:
        with self._lock:
            if message:
                self._errors[stage] = message
            else:
                self._errors.pop(stage, None)

    def track_drops(self, *queues) -> None:
        """Register bounded queues whose drop counters are summed into the report."""
        self._dropped_sources.extend(queues)

    # ---- reporting ----------------------------------------------------------------

    def snapshot(self) -> CameraRuntimeStatus:
        with self._lock:
            error = "; ".join(f"{k}: {v}" for k, v in self._errors.items()) or None
        return CameraRuntimeStatus(
            camera_id=self.camera_id,
            rtsp_status=self.rtsp_status,
            ai_status=self.ai_status,
            stream_status=self.stream_status,
            input_fps=self.input.fps(),
            inference_fps=self.inference.fps(),
            output_fps=self.output.fps(),
            resolution=self.resolution,
            last_frame_at=self.last_frame_at,
            dropped_frames=sum(q.dropped for q in self._dropped_sources),
            error=error,
        )

    def state_key(self) -> tuple:
        """Changes of these values trigger an immediate status report."""
        return (self.rtsp_status, self.ai_status, self.stream_status)
