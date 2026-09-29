"""Encodes an annotated JPEG and uploads it straight to MinIO via a backend-issued presigned URL."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from agent.api_client.client import ApiError, BackendClient
from agent.inference.base import Detection

logger = logging.getLogger(__name__)


def annotate(frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
    out = frame.copy()
    for d in detections:
        p1, p2 = (int(d.bbox.x1), int(d.bbox.y1)), (int(d.bbox.x2), int(d.bbox.y2))
        cv2.rectangle(out, p1, p2, (0, 200, 255), 2)
        cv2.putText(out, f"{d.class_name} {d.confidence:.2f}", (p1[0], max(p1[1] - 8, 16)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
    return out


class SnapshotUploader:
    def __init__(self, client: BackendClient, jpeg_quality: int = 80) -> None:
        self._client = client
        self._quality = jpeg_quality

    def upload(self, camera_id: str, frame: np.ndarray, detections: list[Detection]) -> str | None:
        """Returns the object key, or None if the upload failed (the event is still sent)."""
        ok, buf = cv2.imencode(".jpg", annotate(frame, detections), [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        if not ok:
            return None
        try:
            presigned = self._client.presign_snapshot(camera_id)
            self._client.upload(presigned.upload_url, buf.tobytes(), "image/jpeg")
            return presigned.object_key
        except ApiError as exc:
            logger.warning("snapshot upload failed: %s", exc)
            return None
