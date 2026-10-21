from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, db: DBSession) -> TokenPair:
    return await AuthService(db).login(body.username, body.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DBSession) -> TokenPair:
    return await AuthService(db).refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: DBSession, _: CurrentUser) -> None:
    await AuthService(db).logout(body.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
