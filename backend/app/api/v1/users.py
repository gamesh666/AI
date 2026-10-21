import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DBSession, Pagination
from app.core.exceptions import DomainError
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=Page[UserRead])
async def list_users(db: DBSession, _: AdminUser, pagination: Pagination) -> Page[UserRead]:
    return await UserService(db).list(pagination)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: DBSession, _: AdminUser) -> UserRead:
    return UserRead.model_validate(await UserService(db).create(body))


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, db: DBSession, _: AdminUser) -> UserRead:
    return UserRead.model_validate(await UserService(db).get(user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: uuid.UUID, body: UserUpdate, db: DBSession, _: AdminUser) -> UserRead:
    return UserRead.model_validate(await UserService(db).update(user_id, body))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, db: DBSession, admin: AdminUser) -> None:
    if user_id == admin.id:
        raise DomainError("you cannot delete yourself")
    await UserService(db).delete(user_id)
