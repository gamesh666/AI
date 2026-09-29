from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.auth import TokenPair


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)

    async def login(self, username: str, password: str) -> TokenPair:
        user = await self.users.get_by_username(username)
        if not user or not user.is_active or not verify_password(password, user.hashed_password):
            raise AuthError("invalid username or password")
        pair = await self._issue(user)
        await self.session.commit()
        return pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        stored = await self.tokens.get_by_hash(hash_token(refresh_token))
        now = datetime.now(UTC)
        if stored is None:
            raise AuthError("invalid refresh token")
        if stored.revoked_at is not None:
            # reuse of a rotated token => likely theft: revoke the whole family
            await self.tokens.revoke_all_for_user(stored.user_id)
            await self.session.commit()
            raise AuthError("refresh token reused")
        if stored.expires_at < now:
            raise AuthError("refresh token expired")
        user = await self.users.get(stored.user_id)
        if not user or not user.is_active:
            raise AuthError("user disabled")
        stored.revoked_at = now  # rotation
        pair = await self._issue(user)
        await self.session.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        stored = await self.tokens.get_by_hash(hash_token(refresh_token))
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _issue(self, user: User) -> TokenPair:
        settings = get_settings()
        access, ttl = create_access_token(user.id, user.role.value)
        refresh = generate_opaque_token()
        await self.tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh),
                expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
            )
        )
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=ttl)
