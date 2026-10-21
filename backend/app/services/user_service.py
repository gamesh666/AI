from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.common import Page, PageParams
from app.schemas.user import UserCreate, UserRead, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def list(self, params: PageParams) -> Page[UserRead]:
        rows, total = await self.repo.paginate(self.repo.list_stmt(), params.offset, params.page_size)
        return Page(
            items=[UserRead.model_validate(u) for u in rows],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("user not found")
        return user

    async def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump(exclude={"password"}), hashed_password=hash_password(data.password))
        try:
            await self.repo.add(user)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("username or email already exists") from exc
        return user

    async def update(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = await self.get(user_id)
        changes = data.model_dump(exclude_unset=True)
        if password := changes.pop("password", None):
            user.hashed_password = hash_password(password)
        self.repo.apply_updates(user, changes)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("email already exists") from exc
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: uuid.UUID) -> None:
        await self.repo.delete(await self.get(user_id))
        await self.session.commit()
