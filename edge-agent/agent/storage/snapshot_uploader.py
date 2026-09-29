"""Uploads an (already annotated) JPEG snapshot straight to MinIO via a backend-issued presigned URL."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from agent.api_client.client import ApiError, BackendClient

logger = logging.getLogger(__name__)


class SnapshotUploader:
    def __init__(self, client: BackendClient, jpeg_quality: int = 80) -> None:
        self._client = client
        self._quality = jpeg_quality

    def upload(self, camera_uuid: str, image: np.ndarray) -> str | None:
        """Returns the object key, or None if the upload failed (the event is still sent)."""
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        if not ok:
            return None
        try:
            presigned = self._client.presign_snapshot(camera_uuid)
            self._client.upload(presigned.upload_url, buf.tobytes(), "image/jpeg")
            return presigned.object_key
        except ApiError as exc:
            logger.warning("snapshot upload failed: %s", exc)
            return None
