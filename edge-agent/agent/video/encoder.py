"""Video encoder abstraction: raw BGR frames in → H.264 elementary stream out to a publish target.

    VideoEncoder (interface)
     ├─ FFmpegEncoder      libx264 (CPU) or h264_nvenc (NVIDIA), selected automatically
     ├─ NVENCEncoder       FFmpegEncoder forced to h264_nvenc
     └─ GStreamerEncoder   placeholder (nvv4l2h264enc on Jetson, …)
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


class EncoderError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class EncoderSettings:
    width: int
    height: int
    fps: int = 25
    codec: str = "h264"
    bitrate: str = "2M"
    gop_size: int = 50
    encoder: str = "auto"  # auto | libx264 | h264_nvenc


def parse_bitrate(value: str) -> int:
    """'4M' -> 4_000_000, '800k' -> 800_000, '1500000' -> 1_500_000."""
    v = value.strip().lower()
    mult = {"k": 1_000, "m": 1_000_000}.get(v[-1:], 1)
    return int(float(v[:-1] if mult != 1 else v) * mult)


@functools.lru_cache(maxsize=4)
def nvenc_available(ffmpeg: str) -> bool:
    """h264_nvenc compiled into ffmpeg AND an NVIDIA device visible to this container."""
    if not (shutil.which("nvidia-smi") or os.path.exists("/dev/nvidia0")):
        return False
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "h264_nvenc" in out


def select_h264_encoder(ffmpeg: str, preference: str = "auto") -> str:
    if preference in ("libx264", "h264_nvenc"):
        return preference
    return "h264_nvenc" if nvenc_available(ffmpeg) else "libx264"


def codec_args(encoder: str, s: EncoderSettings) -> list[str]:
    """Low-latency, WebRTC-friendly H.264: no B-frames, fixed GOP, CBR-ish rate control."""
    rate = parse_bitrate(s.bitrate)
    common = ["-g", str(s.gop_size), "-keyint_min", str(s.gop_size), "-bf", "0",
              "-b:v", str(rate), "-maxrate", str(rate), "-bufsize", str(rate * 2), "-pix_fmt", "yuv420p"]
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll", "-rc", "cbr", "-zerolatency", "1",
                "-profile:v", "baseline", *common]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-profile:v", "baseline",
            "-sc_threshold", "0", *common]


class VideoEncoder(ABC):
    name = "base"

    @abstractmethod
    def start(self, output_url: str, output_format: str, extra_output_args: list[str] | None = None) -> None:
        """Start encoding to `output_url` (muxer `output_format`: rtsp, mpegts, …)."""

    @abstractmethod
    def write(self, image: np.ndarray) -> None:
        """Encode one BGR frame of exactly settings.width x settings.height. Raises EncoderError."""

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def alive(self) -> bool: ...


class FFmpegEncoder(VideoEncoder):
    """Runs `ffmpeg -f rawvideo -i - … <output>`; frames are written to stdin.

    A watchdog kills ffmpeg if a single write blocks longer than `write_timeout` (e.g. the network
    stalled), turning a hang into an EncoderError the publisher can recover from.
    """

    name = "ffmpeg"

    def __init__(self, settings: EncoderSettings, ffmpeg: str = "ffmpeg", write_timeout: float = 5.0) -> None:
        self.settings = settings
        self._ffmpeg = ffmpeg
        self._write_timeout = write_timeout
        self._proc: subprocess.Popen | None = None
        self._stderr: deque[str] = deque(maxlen=20)
        self._write_started: float | None = None
        self._watchdog_stop = threading.Event()
        self.encoder = select_h264_encoder(ffmpeg, settings.encoder)

    def build_command(self, output_url: str, output_format: str,
                      extra_output_args: list[str] | None = None) -> list[str]:
        s = self.settings
        return [
            self._ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{s.width}x{s.height}", "-r", str(s.fps), "-i", "-",
            "-an", *codec_args(self.encoder, s),
            *(extra_output_args or []),
            "-f", output_format, output_url,
        ]

    def start(self, output_url: str, output_format: str, extra_output_args: list[str] | None = None) -> None:
        if not shutil.which(self._ffmpeg):
            raise EncoderError(f"ffmpeg not found ({self._ffmpeg})")
        cmd = self.build_command(output_url, output_format, extra_output_args)
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE, bufsize=0)
        threading.Thread(target=self._drain_stderr, args=(self._proc,), daemon=True).start()
        self._watchdog_stop.clear()
        threading.Thread(target=self._watchdog, daemon=True).start()
        logger.info("encoder started: %s %dx%d@%d %s", self.encoder, self.settings.width, self.settings.height,
                    self.settings.fps, self.settings.bitrate)

    def write(self, image: np.ndarray) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            raise EncoderError(self._failure("encoder not running"))
        if image.shape[1] != self.settings.width or image.shape[0] != self.settings.height:
            raise EncoderError(f"frame size {image.shape[1]}x{image.shape[0]} != encoder size")
        self._write_started = time.monotonic()
        try:
            proc.stdin.write(np.ascontiguousarray(image).tobytes())
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise EncoderError(self._failure(str(exc))) from exc
        finally:
            self._write_started = None

    def close(self) -> None:
        self._watchdog_stop.set()
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    _NOISE = ("Terminating", "Task finished", "Conversion failed", "Error writing trailer", "Exiting normally")

    def error_detail(self) -> str:
        """Most informative recent ffmpeg error line (skips generic shutdown noise)."""
        lines = [line for line in self._stderr if not any(n in line for n in self._NOISE)]
        return (lines or list(self._stderr) or [""])[-1][:200]

    def _failure(self, reason: str) -> str:
        detail = " | ".join(list(self._stderr)[-2:])
        return f"{reason}{' — ' + detail if detail else ''}"

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        assert proc.stderr is not None
        for raw in iter(proc.stderr.readline, b""):
            line = raw.decode(errors="replace").rstrip()
            if line:
                self._stderr.append(line)

    def _watchdog(self) -> None:
        while not self._watchdog_stop.wait(1.0):
            started = self._write_started
            if started is not None and time.monotonic() - started > self._write_timeout and self._proc:
                logger.warning("encoder write blocked > %.0fs; killing ffmpeg", self._write_timeout)
                self._proc.kill()
                return


class NVENCEncoder(FFmpegEncoder):
    name = "nvenc"

    def __init__(self, settings: EncoderSettings, ffmpeg: str = "ffmpeg", write_timeout: float = 5.0) -> None:
        super().__init__(settings, ffmpeg, write_timeout)
        self.encoder = "h264_nvenc"


class GStreamerEncoder(VideoEncoder):
    """Placeholder for GStreamer pipelines (e.g. appsrc ! nvvidconv ! nvv4l2h264enc ! rtspclientsink)."""

    name = "gstreamer"

    def __init__(self, settings: EncoderSettings) -> None:
        self.settings = settings

    def start(self, output_url: str, output_format: str, extra_output_args: list[str] | None = None) -> None:
        raise NotImplementedError("GStreamerEncoder is not implemented yet")

    def write(self, image: np.ndarray) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    @property
    def alive(self) -> bool:
        return False


def create_encoder(settings: EncoderSettings, ffmpeg: str = "ffmpeg") -> VideoEncoder:
    if settings.encoder == "h264_nvenc":
        return NVENCEncoder(settings, ffmpeg)
    if settings.encoder == "gstreamer":
        return GStreamerEncoder(settings)
    return FFmpegEncoder(settings, ffmpeg)
