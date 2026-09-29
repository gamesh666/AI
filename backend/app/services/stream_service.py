"""Playback URL issuing and the MediaMTX HTTP auth hook.

MediaMTX paths:  ai/<site>/<device>/<camera>        annotated stream (published by the edge)
                 original/<site>/<device>/<camera>  optional passthrough of the raw camera stream
"""

from __future__ import annotations

import logging
import uuid
from urllib.parse import parse_qs

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import StreamStatus, StreamType
from app.core.exceptions import DomainError
from app.core.security import TOKEN_TYPE_STREAM, TokenError, create_stream_token, decode_token, hash_token
from app.models.camera import Camera
from app.models.user import User
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.stream import MediaMTXAuthRequest, StreamInfo
from app.services.camera_service import CameraService

logger = logging.getLogger(__name__)

READ_ACTIONS = {"read", "playback"}


def split_stream_path(path: str) -> tuple[StreamType, str] | None:
    """'original/site01/edge01/cam01' -> (ORIGINAL, 'ai/site01/edge01/cam01' = the canonical stored path)."""
    prefix, _, rest = path.strip("/").partition("/")
    if not rest or rest.count("/") != 2:
        return None
    try:
        stream_type = StreamType(prefix)
    except ValueError:
        return None
    return stream_type, f"{StreamType.AI.value}/{rest}"


def stream_type_enabled(camera: Camera, stream_type: StreamType) -> bool:
    if not (camera.enabled and camera.stream_enabled):
        return False
    if stream_type == StreamType.ORIGINAL:
        return camera.original_stream_enabled
    return camera.annotated_stream_enabled


class StreamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cameras = CameraRepository(session)
        self.devices = DeviceRepository(session)

    async def stream_info(self, camera_id: uuid.UUID, user: User, stream_type: StreamType) -> StreamInfo:
        camera = await CameraService(self.session).get(camera_id)
        if not stream_type_enabled(camera, stream_type):
            raise DomainError(f"{stream_type.value} stream is not enabled for this camera")
        path = camera.stream_path if stream_type == StreamType.AI else camera.original_stream_path
        settings = get_settings()
        token, ttl = create_stream_token(user.id, path)
        device_online = camera.edge_device.status.value == "online"
        # the original passthrough has no health report of its own; follow the device
        if stream_type == StreamType.AI:
            status = camera.stream_status if device_online else StreamStatus.OFFLINE
        else:
            status = StreamStatus.STREAMING if device_online else StreamStatus.OFFLINE
        return StreamInfo(
            camera_id=camera.id,
            camera_code=camera.code,
            status=status,
            stream_type=stream_type,
            webrtc_url=f"{settings.mediamtx_webrtc_public_url.rstrip('/')}/{path}/whep",
            hls_url=f"{settings.mediamtx_hls_public_url.rstrip('/')}/{path}/index.m3u8",
            token=token,
            expires_in=ttl,
        )

    async def authorize_mediamtx(self, req: MediaMTXAuthRequest) -> bool:
        path = (req.path or "").strip("/")
        if req.action == "publish":
            return await self._authorize_publish(req, path)
        if req.action in READ_ACTIONS:
            return self._authorize_read(req, path)
        # api / metrics / pprof are not exposed publicly; deny by default
        return False

    async def _authorize_publish(self, req: MediaMTXAuthRequest, path: str) -> bool:
        """Edge push: device key must be valid, the device must own the camera, the stream type enabled."""
        if not req.user or not req.password:
            return False
        parsed = split_stream_path(path)
        if parsed is None:
            return False
        stream_type, canonical = parsed
        device = await self.devices.get_by_api_key_hash(hash_token(req.password))
        if device is None or device.device_uuid != req.user:
            return False
        camera = await self.cameras.get_by_stream_path(canonical)
        allowed = (
            camera is not None and camera.edge_device_id == device.id and stream_type_enabled(camera, stream_type)
        )
        if not allowed:
            logger.warning("publish denied device=%s path=%s", req.user, path)
        return allowed

    @staticmethod
    def _authorize_read(req: MediaMTXAuthRequest, path: str) -> bool:
        candidates = [req.token, req.password]
        if req.query:
            candidates.extend(parse_qs(req.query).get("token", []))
        for candidate in filter(None, candidates):
            try:
                claims = decode_token(candidate, TOKEN_TYPE_STREAM)
            except TokenError:
                continue
            if claims.get("path") == path:
                return True
        return False
