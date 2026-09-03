import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    PasswordResetResponse,
    RoleAssignRequest,
    UserCreate,
    UserCreateResponse,
    UserOut,
    UserUpdate,
)
from app.services import auth_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_user_or_404(db: AsyncSession, user_id: str) -> User:
    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_permission("USER_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> UserCreateResponse:
    user, temporary_password = await user_service.create_user(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    user_out = user_service.to_user_out(user)
    return UserCreateResponse(**user_out.model_dump(), temporary_password=temporary_password)


@router.get("", response_model=PaginatedResponse[UserOut])
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    current_user: User = Depends(require_permission("USER_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserOut]:
    users, total = await user_service.list_users(db, skip=skip, limit=limit, search=search)
    return PaginatedResponse(
        items=[user_service.to_user_out(u) for u in users], total=total, skip=skip, limit=limit
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_permission("USER_READ")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    return user_service.to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_permission("USER_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    user = await user_service.update_user(
        db, user, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return user_service.to_user_out(user)


@router.delete("/{user_id}", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_permission("USER_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    user = await user_service.deactivate_user(
        db, user, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return user_service.to_user_out(user)


@router.post("/{user_id}/roles", response_model=UserOut)
async def assign_roles(
    user_id: str,
    payload: RoleAssignRequest,
    request: Request,
    current_user: User = Depends(require_permission("USER_ROLE_ASSIGN")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    user = await user_service.assign_roles(
        db,
        user,
        payload.role_ids,
        current_user,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return user_service.to_user_out(user)


@router.delete("/{user_id}/roles/{role_id}", response_model=UserOut)
async def remove_role(
    user_id: str,
    role_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("USER_ROLE_ASSIGN")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    user = await user_service.remove_role(
        db,
        user,
        role_id,
        current_user,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return user_service.to_user_out(user)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    user_id: str,
    request: Request,
    current_user: User = Depends(require_permission("USER_PASSWORD_RESET")),
    db: AsyncSession = Depends(get_db),
) -> PasswordResetResponse:
    user = await _get_user_or_404(db, user_id)
    user, temporary_password = await auth_service.admin_reset_password(
        db, user, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return PasswordResetResponse(employee_id=user.employee_id, temporary_password=temporary_password)
