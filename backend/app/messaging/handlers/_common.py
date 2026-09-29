from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.messaging.base import IncomingMessage

logger = logging.getLogger("app.messaging")

T = TypeVar("T", bound=BaseModel)


def parse_payload(msg: IncomingMessage, model: type[T]) -> T | None:
    try:
        return model.model_validate_json(msg.payload)
    except ValidationError as exc:
        logger.warning("invalid %s payload on %s: %s", model.__name__, msg.topic, exc.errors()[:3])
        return None
