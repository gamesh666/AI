"""Detector registry.

Pipelines ask for a detector by name (EDGE_DETECTOR / DETECTOR_TYPE) and only ever see the
`Detector` interface — they never know which implementation is running.

Production registers "yolo". Other implementations (e.g. the simulation package's "mock") are
registered at startup through agent.plugins; production code never imports them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from agent.ai.detector import Detection, Detector
from agent.ai.yolo_detector import YoloDetector
from agent.config.models import CameraConfig
from agent.core.frame_queue import Frame

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DetectorOptions:
    device: str = "cuda:0"
    conf: float = 0.25


DetectorFactory = Callable[[CameraConfig, DetectorOptions], Detector]


def _yolo(camera: CameraConfig, opts: DetectorOptions) -> Detector:
    model = camera.ai_model
    if model is None:
        raise ValueError("YOLO detector requires an AI model assigned to the camera")
    return YoloDetector(model_path=model.model_path, labels=model.labels, device=opts.device, conf=opts.conf)


_DETECTORS: dict[str, DetectorFactory] = {"yolo": _yolo}


def register_detector(name: str, factory: DetectorFactory) -> None:
    _DETECTORS[name] = factory


def available_detectors() -> list[str]:
    return sorted(_DETECTORS)


class FallbackDetector(Detector):
    """Tries `primary`; if it cannot load (no model file, no ultralytics, no GPU driver, …) uses `fallback`."""

    def __init__(self, primary: Detector, fallback: Detector) -> None:
        super().__init__(primary.labels)
        self._primary = primary
        self._fallback = fallback
        self._active: Detector = primary

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._active.name

    def load(self) -> None:
        try:
            self._primary.load()
            self._active = self._primary
        except Exception as exc:
            logger.warning("detector '%s' unavailable (%s); using fallback '%s'",
                           self._primary.name, exc, self._fallback.name)
            self._fallback.load()
            self._active = self._fallback

    def detect(self, frame: Frame) -> list[Detection]:
        return self._active.detect(frame)

    def close(self) -> None:
        self._primary.close()
        self._fallback.close()


def _build(name: str, camera: CameraConfig, opts: DetectorOptions) -> Detector:
    try:
        factory = _DETECTORS[name]
    except KeyError:
        raise ValueError(f"unknown detector '{name}' (available: {', '.join(available_detectors())}); "
                         "is the plugin that provides it listed in EDGE_PLUGINS?") from None
    return factory(camera, opts)


def create_detector(name: str, camera: CameraConfig, opts: DetectorOptions | None = None,
                    fallback: str | None = None) -> Detector:
    opts = opts or DetectorOptions()
    if fallback and fallback != name:
        try:
            primary = _build(name, camera, opts)
        except ValueError as exc:  # e.g. no model assigned
            logger.warning("detector '%s' not usable for %s (%s); using '%s'", name, camera.camera_id, exc, fallback)
            return _build(fallback, camera, opts)
        return FallbackDetector(primary, _build(fallback, camera, opts))
    return _build(name, camera, opts)
