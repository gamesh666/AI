"""Idempotent bootstrap: creates the initial admin (from env) and a default AI model.

    python -m app.cli.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import dispose_engine, get_session_factory
from app.models.ai_model import AIModel
from app.models.camera import Camera
from app.models.edge_device import EdgeDevice
from app.models.site import Site
from app.models.user import User
from app.services.camera_service import build_stream_path

logger = logging.getLogger("seed")

COCO_LABELS_HEAD = ["person", "bicycle", "car", "motorcycle", "bus", "truck", "dog", "cat"]


async def seed() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        admins = await session.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))
        if not admins:
            if settings.initial_admin_password is None:
                logger.warning("no admin exists and INITIAL_ADMIN_PASSWORD is not set; skipping admin seed")
            else:
                session.add(
                    User(
                        username=settings.initial_admin_username,
                        email=settings.initial_admin_email,
                        full_name="Administrator",
                        hashed_password=hash_password(settings.initial_admin_password.get_secret_value()),
                        role=UserRole.ADMIN,
                    )
                )
                logger.info("created initial admin '%s'", settings.initial_admin_username)

        if not await session.scalar(select(func.count()).select_from(AIModel)):
            session.add(
                AIModel(
                    name="yolov8n",
                    version="8.0",
                    model_type="yolov8",
                    labels=COCO_LABELS_HEAD,
                    model_path="models/yolov8n.pt",
                    description="Default YOLOv8 nano (COCO). Edge agents use the mock detector until YOLO is enabled.",
                )
            )
            logger.info("created default AI model yolov8n")
        await session.flush()
        if settings.seed_demo_data:
            await _seed_demo(session, settings.demo_device_uuid)
        try:
            await session.commit()
        except IntegrityError:
            # another replica seeded concurrently
            await session.rollback()
            logger.info("seed data already present")
    await dispose_engine()


async def _seed_demo(session, device_uuid: str) -> None:
    """Demo site + device + two synthetic cameras. The device key is issued when the agent registers."""
    if await session.scalar(select(EdgeDevice).where(EdgeDevice.device_uuid == device_uuid)):
        return
    site = await session.scalar(select(Site).where(Site.code == "site01"))
    if site is None:
        site = Site(name="Demo Site", code="site01", address="Localhost", description="Created by SEED_DEMO_DATA")
        session.add(site)
    model = await session.scalar(select(AIModel).order_by(AIModel.created_at).limit(1))
    device = EdgeDevice(device_uuid=device_uuid, name="Demo Edge", site=site)
    session.add(device)
    for idx, name in ((1, "Entrance"), (2, "Parking")):
        code = f"cam{idx:02d}"
        session.add(
            Camera(
                edge_device=device,
                code=code,
                name=f"Demo {name}",
                # synthetic source rendered on the edge; replace with rtsp://<camera-ip>/... for real cameras
                rtsp_url=f"mock://scene?seed={idx}",
                stream_path=build_stream_path(site.code, device_uuid, code),
                resolution="1280x720",
                stream_fps=25,
                inference_fps=5,
                bitrate="2M",
                gop_size=50,
                ai_model_id=model.id if model else None,
            )
        )
    logger.info("created demo site/device/cameras for %s", device_uuid)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed())
