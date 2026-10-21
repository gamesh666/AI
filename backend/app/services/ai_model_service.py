from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.ai_model import AIModel
from app.repositories.ai_model_repository import AIModelRepository
from app.schemas.ai_model import AIModelCreate, AIModelRead, AIModelUpdate
from app.schemas.common import Page, PageParams


class AIModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AIModelRepository(session)

    async def list(self, params: PageParams) -> Page[AIModelRead]:
        rows, total = await self.repo.paginate(self.repo.list_stmt(), params.offset, params.page_size)
        return Page(
            items=[AIModelRead.model_validate(m) for m in rows],
            total=total, page=params.page, page_size=params.page_size,
        )

    async def get(self, model_id: uuid.UUID) -> AIModel:
        model = await self.repo.get(model_id)
        if not model:
            raise NotFoundError("AI model not found")
        return model

    async def create(self, data: AIModelCreate) -> AIModel:
        model = AIModel(**data.model_dump())
        try:
            await self.repo.add(model)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("model name+version already exists") from exc
        return model

    async def update(self, model_id: uuid.UUID, data: AIModelUpdate) -> AIModel:
        model = self.repo.apply_updates(await self.get(model_id), data.model_dump(exclude_unset=True))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("model name+version already exists") from exc
        await self.session.refresh(model)
        return model

    async def delete(self, model_id: uuid.UUID) -> None:
        await self.repo.delete(await self.get(model_id))
        await self.session.commit()
