"""Stream URL issuing and the MediaMTX HTTP auth hook."""

from __future__ import annotations

import logging
import uuid
from urllib.parse import parse_qs

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import TOKEN_TYPE_STREAM, TokenError, create_stream_token, decode_token, hash_token
from app.models.user import User
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.stream import MediaMTXAuthRequest, StreamInfo
from app.services.camera_service import CameraService

logger = logging.getLogger(__name__)

READ_ACTIONS = {"read", "playback"}


class StreamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cameras = CameraRepository(session)
        self.devices = DeviceRepository(session)

    async def stream_info(self, camera_id: uuid.UUID, user: User) -> StreamInfo:
        camera = await CameraService(self.session).get(camera_id)
        settings = get_settings()
        token, ttl = create_stream_token(user.id, camera.stream_id)
        return StreamInfo(
            camera_id=camera.id,
            stream_id=camera.stream_id,
            webrtc_url=f"{settings.mediamtx_webrtc_public_url.rstrip('/')}/{camera.stream_id}/whep",
            hls_url=f"{settings.mediamtx_hls_public_url.rstrip('/')}/{camera.stream_id}/index.m3u8",
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
        if not req.user or not req.password:
            return False
        device = await self.devices.get_by_api_key_hash(hash_token(req.password))
        if device is None or device.device_uuid != req.user:
            return False
        camera = await self.cameras.get_by_stream_id(path)
        allowed = camera is not None and camera.edge_device_id == device.id and camera.enabled
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
