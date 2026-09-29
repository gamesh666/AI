"""Password hashing, JWT and opaque token helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_STREAM = "stream"


class TokenError(Exception):
    pass


# ---- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# ---- opaque tokens (refresh tokens, device keys) -------------------------------


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Deterministic hash for high-entropy opaque tokens (lookup by hash)."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


# ---- JWT ---------------------------------------------------------------------


def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + expires_delta, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise TokenError("unexpected token type")
    return payload


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    ttl = settings.access_token_expire_minutes * 60
    token = _encode({"sub": str(user_id), "role": role, "type": TOKEN_TYPE_ACCESS}, timedelta(seconds=ttl))
    return token, ttl


def create_stream_token(user_id: uuid.UUID, stream_path: str) -> tuple[str, int]:
    """Short-lived token that lets a browser read exactly one MediaMTX path."""
    settings = get_settings()
    ttl = settings.stream_token_expire_seconds
    token = _encode(
        {"sub": str(user_id), "path": stream_path, "type": TOKEN_TYPE_STREAM},
        timedelta(seconds=ttl),
    )
    return token, ttl
