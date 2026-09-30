"""Idempotent bootstrap: creates the initial admin (from env) and a default AI model.

Demo sites / devices / cameras are NOT created here: see simulation/ (demo-seed, public API only).

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
from app.models.user import User

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
                    description="Default YOLOv8 nano (COCO).",
                )
            )
            logger.info("created default AI model yolov8n")
        try:
            await session.commit()
        except IntegrityError:
            # another replica seeded concurrently
            await session.rollback()
            logger.info("seed data already present")
    await dispose_engine()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed())
