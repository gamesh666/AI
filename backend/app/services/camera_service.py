from __future__ import annotations

import secrets
import uuid
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.exceptions import ConflictError, NotFoundError
from app.messaging import publisher
from app.models.camera import Camera
from app.repositories.ai_model_repository import AIModelRepository
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.schemas.common import Page, PageParams
from app.services.mappers import camera_to_read


def split_credentials(url: str) -> tuple[str, str | None, str | None]:
    """'rtsp://u:p@host:554/x' -> ('rtsp://host:554/x', 'u', 'p')."""
    parts = urlsplit(url)
    if not (parts.username or parts.password):
        return url, None, None
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    clean = urlunsplit(parts._replace(netloc=host))
    user = unquote(parts.username) if parts.username else None
    password = unquote(parts.password) if parts.password else None
    return clean, user, password


def build_authenticated_url(camera: Camera) -> str:
    """Rebuild the full RTSP URL (with credentials). Only for the owning edge device."""
    if not camera.rtsp_username and not camera.rtsp_password_encrypted:
        return camera.rtsp_url
    parts = urlsplit(camera.rtsp_url)
    user = quote(camera.rtsp_username or "", safe="")
    password = decrypt_secret(camera.rtsp_password_encrypted) if camera.rtsp_password_encrypted else ""
    userinfo = f"{user}:{quote(password, safe='')}" if password else user
    return urlunsplit(parts._replace(netloc=f"{userinfo}@{parts.netloc}"))


def generate_stream_id() -> str:
    return f"cam-{secrets.token_hex(4)}"


class CameraService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CameraRepository(session)
        self.devices = DeviceRepository(session)
        self.models = AIModelRepository(session)

    async def list(
        self,
        params: PageParams,
        site_id: uuid.UUID | None = None,
        edge_device_id: uuid.UUID | None = None,
        enabled: bool | None = None,
    ) -> Page[CameraRead]:
        rows, total = await self.repo.paginate(
            self.repo.list_stmt(site_id, edge_device_id, enabled), params.offset, params.page_size
        )
        return Page(
            items=[camera_to_read(c) for c in rows], total=total, page=params.page, page_size=params.page_size
        )

    async def get(self, camera_id: uuid.UUID) -> Camera:
        camera = await self.repo.get_full(camera_id)
        if not camera:
            raise NotFoundError("camera not found")
        return camera

    async def get_read(self, camera_id: uuid.UUID) -> CameraRead:
        return camera_to_read(await self.get(camera_id))

    async def create(self, data: CameraCreate) -> CameraRead:
        device = await self.devices.get(data.edge_device_id)
        if not device:
            raise NotFoundError("edge device not found")
        await self._check_model(data.ai_model_id)

        clean_url, url_user, url_pass = split_credentials(data.rtsp_url)
        username = data.rtsp_username or url_user
        password = data.rtsp_password or url_pass
        camera = Camera(
            edge_device_id=data.edge_device_id,
            name=data.name,
            rtsp_url=clean_url,
            rtsp_username=username,
            rtsp_password_encrypted=encrypt_secret(password) if password else None,
            onvif_url=data.onvif_url,
            stream_id=data.stream_id or generate_stream_id(),
            enabled=data.enabled,
            ai_enabled=data.ai_enabled,
            ai_model_id=data.ai_model_id,
        )
        try:
            await self.repo.add(camera)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("stream_id already exists") from exc
        await publisher.notify_config_changed(device.device_uuid, "camera_created")
        return await self.get_read(camera.id)

    async def update(self, camera_id: uuid.UUID, data: CameraUpdate) -> CameraRead:
        camera = await self.get(camera_id)
        old_device_uuid = camera.edge_device.device_uuid
        changes = data.model_dump(exclude_unset=True)

        if "ai_model_id" in changes:
            await self._check_model(changes["ai_model_id"])
        if changes.get("edge_device_id") and not await self.devices.get(changes["edge_device_id"]):
            raise NotFoundError("edge device not found")

        if "rtsp_url" in changes and changes["rtsp_url"]:
            clean_url, url_user, url_pass = split_credentials(changes.pop("rtsp_url"))
            camera.rtsp_url = clean_url
            if url_user is not None:
                camera.rtsp_username = url_user
            if url_pass is not None:
                camera.rtsp_password_encrypted = encrypt_secret(url_pass)
        if "rtsp_username" in changes:
            camera.rtsp_username = changes.pop("rtsp_username") or None
        if "rtsp_password" in changes:
            password = changes.pop("rtsp_password")
            camera.rtsp_password_encrypted = encrypt_secret(password) if password else None

        self.repo.apply_updates(camera, changes)
        await self.session.commit()

        camera = await self.get(camera_id)
        await publisher.notify_config_changed(camera.edge_device.device_uuid, "camera_updated")
        if camera.edge_device.device_uuid != old_device_uuid:
            await publisher.notify_config_changed(old_device_uuid, "camera_moved")
        return camera_to_read(camera)

    async def delete(self, camera_id: uuid.UUID) -> None:
        camera = await self.get(camera_id)
        device_uuid = camera.edge_device.device_uuid
        await self.repo.delete(camera)
        await self.session.commit()
        await publisher.notify_config_changed(device_uuid, "camera_deleted")

    async def _check_model(self, model_id: uuid.UUID | None) -> None:
        if model_id and not await self.models.get(model_id):
            raise NotFoundError("AI model not found")
