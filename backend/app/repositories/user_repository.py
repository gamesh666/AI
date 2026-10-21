from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.user import RefreshToken, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> User | None:
        return await self.get_by(username=username)

    def list_stmt(self):
        return select(User).order_by(User.username)


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.get_by(token_hash=token_hash)

    async def revoke_all_for_user(self, user_id) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
