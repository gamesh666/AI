from __future__ import annotations

import uuid
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.enums import StreamType
from app.core.exceptions import ConflictError, NotFoundError
from app.messaging import publisher
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.repositories.ai_model_repository import AIModelRepository
from app.repositories.camera_repository import CameraRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.schemas.common import Page, PageParams
from app.services.mappers import camera_to_read

UNASSIGNED_SITE = "unassigned"

# settings a camera update may change directly (validated by the schema)
_STREAM_FIELDS = (
    "stream_enabled", "annotated_stream_enabled", "original_stream_enabled",
    "resolution", "stream_fps", "inference_fps", "bitrate", "gop_size",
)


def build_stream_path(site_code: str | None, device_uuid: str, camera_code: str,
                      stream_type: StreamType = StreamType.AI) -> str:
    """ai/<site>/<device>/<camera> — built from system IDs, never from the camera's IP address."""
    return f"{stream_type.value}/{site_code or UNASSIGNED_SITE}/{device_uuid}/{camera_code}"


def stream_path_for(camera: Camera, device: EdgeDevice, stream_type: StreamType = StreamType.AI) -> str:
    return build_stream_path(device.site.code if device.site else None, device.device_uuid, camera.code, stream_type)


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

    async def _device(self, device_id: uuid.UUID) -> EdgeDevice:
        device = await self.devices.get(device_id)
        if not device:
            raise NotFoundError("edge device not found")
        await self.session.refresh(device, ["site"])
        return device

    async def create(self, data: CameraCreate) -> CameraRead:
        device = await self._device(data.edge_device_id)
        await self._check_model(data.ai_model_id)

        clean_url, url_user, url_pass = split_credentials(data.rtsp_url)
        username = data.rtsp_username or url_user
        password = data.rtsp_password or url_pass
        camera = Camera(
            edge_device_id=device.id,
            code=data.code,
            name=data.name,
            rtsp_url=clean_url,
            rtsp_username=username,
            rtsp_password_encrypted=encrypt_secret(password) if password else None,
            onvif_url=data.onvif_url,
            enabled=data.enabled,
            ai_enabled=data.ai_enabled,
            ai_model_id=data.ai_model_id,
        )
        for field in _STREAM_FIELDS:
            value = getattr(data, field)
            if value is not None:
                setattr(camera, field, value)
        camera.stream_path = stream_path_for(camera, device)
        try:
            await self.repo.add(camera)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("camera code already exists on this edge device") from exc
        await publisher.notify_config_changed(device.device_uuid, "camera_created")
        return await self.get_read(camera.id)

    async def update(self, camera_id: uuid.UUID, data: CameraUpdate) -> CameraRead:
        camera = await self.get(camera_id)
        old_device_uuid = camera.edge_device.device_uuid
        changes = data.model_dump(exclude_unset=True)

        if "ai_model_id" in changes:
            await self._check_model(changes["ai_model_id"])
        device = camera.edge_device
        if changes.get("edge_device_id") and changes["edge_device_id"] != camera.edge_device_id:
            device = await self._device(changes["edge_device_id"])

        if changes.get("rtsp_url"):
            clean_url, url_user, url_pass = split_credentials(changes.pop("rtsp_url"))
            camera.rtsp_url = clean_url
            if url_user is not None:
                camera.rtsp_username = url_user
            if url_pass is not None:
                camera.rtsp_password_encrypted = encrypt_secret(url_pass)
        changes.pop("rtsp_url", None)
        if "rtsp_username" in changes:
            camera.rtsp_username = changes.pop("rtsp_username") or None
        if "rtsp_password" in changes:
            password = changes.pop("rtsp_password")
            camera.rtsp_password_encrypted = encrypt_secret(password) if password else None

        self.repo.apply_updates(camera, changes)
        camera.edge_device = device
        camera.stream_path = stream_path_for(camera, device)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("camera code already exists on this edge device") from exc

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

    async def refresh_stream_paths(self, device: EdgeDevice) -> None:
        """Re-derive stream paths after the device moved site or the site code changed (caller commits)."""
        await self.session.refresh(device, ["site"])
        for camera in await self.repo.list_for_device(device.id):
            camera.stream_path = stream_path_for(camera, device)

    async def _check_model(self, model_id: uuid.UUID | None) -> None:
        if model_id and not await self.models.get(model_id):
            raise NotFoundError("AI model not found")
