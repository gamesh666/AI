from __future__ import annotations

from agent.inference.base import Detection
from aivms_shared.payloads import BBox, DetectionEvent
from aivms_shared.payloads import Detection as DetectionPayload


def build_event(
    device_uuid: str,
    camera_id: str,
    model_name: str,
    detections: list[Detection],
    frame_shape: tuple[int, ...],
    snapshot_key: str | None,
) -> DetectionEvent:
    return DetectionEvent(
        device_id=device_uuid,
        camera_id=camera_id,
        model=model_name,
        snapshot_key=snapshot_key,
        frame_height=int(frame_shape[0]),
        frame_width=int(frame_shape[1]),
        detections=[
            DetectionPayload(
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                bbox=BBox(x1=d.bbox.x1, y1=d.bbox.y1, x2=d.bbox.x2, y2=d.bbox.y2),
            )
            for d in detections
        ],
    )
