"""MinIO object storage: snapshot upload/download via presigned URLs.

Edge agents upload snapshots directly to MinIO with a presigned PUT, so image bytes never pass
through the API servers. Browsers download with a short-lived presigned GET.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from urllib.parse import urlparse

from minio import Minio

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _client_for(url_or_endpoint: str, secure_default: bool) -> Minio:
    settings = get_settings()
    if "://" in url_or_endpoint:
        parsed = urlparse(url_or_endpoint)
        endpoint, secure = parsed.netloc, parsed.scheme == "https"
    else:
        endpoint, secure = url_or_endpoint, secure_default
    # region is fixed so presigning never needs a network round-trip
    return Minio(
        endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=secure,
        region=settings.minio_region,
    )


@lru_cache
def internal_client() -> Minio:
    s = get_settings()
    return _client_for(s.minio_endpoint, s.minio_secure)


@lru_cache
def public_client() -> Minio:
    """Signs URLs with the host browsers use (signature covers the Host header)."""
    s = get_settings()
    return _client_for(s.minio_public_url, s.minio_secure)


@lru_cache
def edge_client() -> Minio:
    s = get_settings()
    return _client_for(s.minio_edge_url, s.minio_secure)


def build_snapshot_key(device_uuid: str, camera_id: uuid.UUID | str, ext: str = "jpg") -> str:
    now = datetime.now(UTC)
    # bucket is already "snapshots": key = yyyy/mm/dd/<device>/<camera>/<uuid>.jpg
    return f"{now:%Y/%m/%d}/{device_uuid}/{camera_id}/{uuid.uuid4().hex}.{ext}"


def key_belongs_to_device(key: str, device_uuid: str) -> bool:
    parts = key.split("/")
    return len(parts) == 6 and parts[3] == device_uuid and ".." not in parts and "" not in parts


async def ensure_buckets() -> None:
    s = get_settings()

    def _ensure() -> None:
        client = internal_client()
        if not client.bucket_exists(s.minio_bucket_snapshots):
            client.make_bucket(s.minio_bucket_snapshots)
            logger.info("created bucket %s", s.minio_bucket_snapshots)

    await asyncio.to_thread(_ensure)


def presign_upload(key: str, expires_seconds: int = 300) -> str:
    s = get_settings()
    return edge_client().presigned_put_object(
        s.minio_bucket_snapshots, key, expires=timedelta(seconds=expires_seconds)
    )


def presign_download(key: str | None) -> str | None:
    if not key:
        return None
    s = get_settings()
    try:
        return public_client().presigned_get_object(
            s.minio_bucket_snapshots, key, expires=timedelta(seconds=s.snapshot_url_expire_seconds)
        )
    except Exception:
        logger.exception("failed to presign %s", key)
        return None
