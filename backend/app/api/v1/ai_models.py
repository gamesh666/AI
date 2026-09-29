import uuid

from fastapi import APIRouter, status

from app.api.deps import DBSession, OperatorUser, Pagination, ViewerUser
from app.schemas.ai_model import AIModelCreate, AIModelRead, AIModelUpdate
from app.schemas.common import Page
from app.services.ai_model_service import AIModelService

router = APIRouter()


@router.get("", response_model=Page[AIModelRead])
async def list_models(db: DBSession, _: ViewerUser, pagination: Pagination) -> Page[AIModelRead]:
    return await AIModelService(db).list(pagination)


@router.post("", response_model=AIModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(body: AIModelCreate, db: DBSession, _: OperatorUser) -> AIModelRead:
    return AIModelRead.model_validate(await AIModelService(db).create(body))


@router.get("/{model_id}", response_model=AIModelRead)
async def get_model(model_id: uuid.UUID, db: DBSession, _: ViewerUser) -> AIModelRead:
    return AIModelRead.model_validate(await AIModelService(db).get(model_id))


@router.patch("/{model_id}", response_model=AIModelRead)
async def update_model(model_id: uuid.UUID, body: AIModelUpdate, db: DBSession, _: OperatorUser) -> AIModelRead:
    return AIModelRead.model_validate(await AIModelService(db).update(model_id, body))


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: uuid.UUID, db: DBSession, _: OperatorUser) -> None:
    await AIModelService(db).delete(model_id)
