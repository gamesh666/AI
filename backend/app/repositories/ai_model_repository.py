from __future__ import annotations

from sqlalchemy import select

from app.models.ai_model import AIModel
from app.repositories.base import BaseRepository


class AIModelRepository(BaseRepository[AIModel]):
    model = AIModel

    def list_stmt(self):
        return select(AIModel).order_by(AIModel.name, AIModel.version)

    async def resolve(self, ref: str) -> AIModel | None:
        """Resolve a model reference from an edge payload: 'name' or 'name:version'."""
        name, _, version = ref.partition(":")
        stmt = select(AIModel).where(AIModel.name == name)
        if version:
            stmt = stmt.where(AIModel.version == version)
        stmt = stmt.order_by(AIModel.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()
