"""Generic async repository. Domain repositories add their own query methods."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def paginate(self, stmt: Select, offset: int, limit: int) -> tuple[Sequence[Any], int]:
        total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()
        rows = (await self.session.execute(stmt.offset(offset).limit(limit))).scalars().all()
        return rows, total

    @staticmethod
    def apply_updates(obj: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            setattr(obj, key, value)
        return obj
