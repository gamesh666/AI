"""業主 (owners) and their provisioning tokens. Contract / contact data: operators read, admins write."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, DBSession, OperatorUser
from app.schemas.owner import (
    OwnerCreate,
    OwnerRead,
    OwnerUpdate,
    ProvisioningTokenCreate,
    ProvisioningTokenCreated,
    ProvisioningTokenRead,
)
from app.services.owner_service import OwnerService

router = APIRouter()
tokens_router = APIRouter()


@router.get("", response_model=list[OwnerRead])
async def list_owners(db: DBSession, _: OperatorUser) -> list[OwnerRead]:
    return await OwnerService(db).list()


@router.post("", response_model=OwnerRead, status_code=status.HTTP_201_CREATED)
async def create_owner(body: OwnerCreate, db: DBSession, _: AdminUser) -> OwnerRead:
    return await OwnerService(db).create(body)


@router.patch("/{owner_id}", response_model=OwnerRead)
async def update_owner(owner_id: uuid.UUID, body: OwnerUpdate, db: DBSession, _: AdminUser) -> OwnerRead:
    return await OwnerService(db).update(owner_id, body)


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owner(owner_id: uuid.UUID, db: DBSession, _: AdminUser) -> None:
    await OwnerService(db).delete(owner_id)


@router.get("/{owner_id}/tokens", response_model=list[ProvisioningTokenRead])
async def list_tokens(owner_id: uuid.UUID, db: DBSession, _: AdminUser) -> list[ProvisioningTokenRead]:
    return await OwnerService(db).tokens(owner_id)


@router.post("/{owner_id}/tokens", response_model=ProvisioningTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_token(
    owner_id: uuid.UUID, body: ProvisioningTokenCreate, db: DBSession, user: AdminUser
) -> ProvisioningTokenCreated:
    """The token is in this response only; the platform keeps its hash."""
    return await OwnerService(db).create_token(owner_id, body, user.id)


@tokens_router.post("/{token_id}/revoke", response_model=ProvisioningTokenRead)
async def revoke_token(token_id: uuid.UUID, db: DBSession, _: AdminUser) -> ProvisioningTokenRead:
    return await OwnerService(db).revoke_token(token_id)
