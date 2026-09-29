"""Object tracking: assigns stable track_id values across inference frames.

MVP: IoUTracker — greedy matching per class on IoU, with a center-distance fallback for small or
fast objects that move more than their own size between two (low-FPS) inferences.
The Tracker interface is where ByteTrack or BoT-SORT plug in later;
`predict()` is the hook for Option B (moving boxes between inferences).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from agent.ai.detector import BoundingBox, Detection


class Tracker(ABC):
    @abstractmethod
    def update(self, detections: list[Detection], timestamp: float) -> list[Detection]:
        """Return the detections with track_id assigned."""

    def predict(self, timestamp: float) -> list[Detection] | None:
        """Option B: estimated detections at `timestamp` between inferences (None = not supported)."""
        return None


class NoopTracker(Tracker):
    def update(self, detections: list[Detection], timestamp: float) -> list[Detection]:
        return detections


@dataclass
class _Track:
    track_id: int
    class_name: str
    bbox: BoundingBox
    last_seen: float


def _center_distance_ratio(a: BoundingBox, b: BoundingBox) -> float:
    """Center distance relative to the larger box side (0 = same center)."""
    ax, ay = (a.x1 + a.x2) / 2, (a.y1 + a.y2) / 2
    bx, by = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
    size = max(a.x2 - a.x1, a.y2 - a.y1, b.x2 - b.x1, b.y2 - b.y1, 1.0)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / size


class IoUTracker(Tracker):
    def __init__(self, iou_threshold: float = 0.3, max_age_seconds: float = 2.0,
                 max_center_distance: float = 0.8) -> None:
        self._iou = iou_threshold
        self._max_age = max_age_seconds
        self._max_dist = max_center_distance
        self._tracks: list[_Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection], timestamp: float) -> list[Detection]:
        self._tracks = [t for t in self._tracks if timestamp - t.last_seen <= self._max_age]
        # score every same-class pair: IoU when boxes overlap enough, else a (lower-ranked) distance score
        pairs = []
        for ti, t in enumerate(self._tracks):
            for di, d in enumerate(detections):
                if t.class_name != d.class_name:
                    continue
                iou = t.bbox.iou(d.bbox)
                if iou >= self._iou:
                    pairs.append((1.0 + iou, ti, di))
                else:
                    dist = _center_distance_ratio(t.bbox, d.bbox)
                    if dist <= self._max_dist:
                        pairs.append((1.0 - dist / self._max_dist, ti, di))
        pairs.sort(reverse=True)
        assigned: dict[int, int] = {}
        used_tracks: set[int] = set()
        for _, ti, di in pairs:
            if ti in used_tracks or di in assigned:
                continue
            assigned[di] = ti
            used_tracks.add(ti)

        out = []
        for di, det in enumerate(detections):
            if di in assigned:
                track = self._tracks[assigned[di]]
                track.bbox, track.last_seen = det.bbox, timestamp
            else:
                track = _Track(self._next_id, det.class_name, det.bbox, timestamp)
                self._next_id += 1
                self._tracks.append(track)
            out.append(det.with_track(track.track_id))
        return out


def create_tracker(kind: str) -> Tracker:
    if kind == "iou":
        return IoUTracker()
    if kind in ("none", ""):
        return NoopTracker()
    raise ValueError(f"unknown tracker '{kind}' (bytetrack / botsort are not bundled yet)")
