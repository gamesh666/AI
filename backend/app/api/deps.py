"""FastAPI dependencies: DB session, current user, RBAC, device authentication, pagination."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ROLE_LEVEL, UserRole
from app.core.exceptions import AuthError, PermissionDeniedError
from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.db.session import get_db
from app.models.edge_device import EdgeDevice
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.common import PageParams
from app.services.device_service import DeviceService

DBSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise AuthError("not authenticated")
    try:
        claims = decode_token(credentials.credentials, TOKEN_TYPE_ACCESS)
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, KeyError, ValueError) as exc:
        raise AuthError("invalid or expired token") from exc
    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AuthError("user not found or disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: UserRole):
    """RBAC: admin > operator > viewer."""

    async def _check(user: CurrentUser) -> User:
        if ROLE_LEVEL[user.role] < ROLE_LEVEL[minimum]:
            raise PermissionDeniedError(f"requires role '{minimum.value}' or higher")
        return user

    return _check


ViewerUser = Annotated[User, Depends(require_role(UserRole.VIEWER))]
OperatorUser = Annotated[User, Depends(require_role(UserRole.OPERATOR))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


async def get_current_device(
    db: DBSession, x_device_key: Annotated[str | None, Header()] = None
) -> EdgeDevice:
    if not x_device_key:
        raise AuthError("missing X-Device-Key")
    return await DeviceService(db).authenticate(x_device_key)


CurrentDevice = Annotated[EdgeDevice, Depends(get_current_device)]


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


Pagination = Annotated[PageParams, Depends(page_params)]
