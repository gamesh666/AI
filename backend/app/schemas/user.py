from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole
from app.schemas.common import ORMModel


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=128)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=256)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)


class UserRead(ORMModel):
    id: uuid.UUID
    username: str
    email: str | None
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
