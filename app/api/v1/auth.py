from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import login_rate_limiter
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    SelfUpdateRequest,
    TokenResponse,
)
from app.schemas.user import UserOut, UserUpdate
from app.services import auth_service, user_service
from app.services.permission_service import get_user_permission_codes
from app.services.user_service import to_user_out

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limiter)])
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user, access_token, refresh_token = await auth_service.login(
        db, payload.email, payload.password, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    access_token, refresh_token = await auth_service.refresh_session(
        db, payload.refresh_token, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return RefreshResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await auth_service.logout(
        db,
        payload.refresh_token,
        current_user,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MeResponse:
    permissions = await get_user_permission_codes(db, current_user.employee_id)
    user_out = to_user_out(current_user)
    return MeResponse(
        **user_out.model_dump(),
        permissions=sorted(permissions),
    )


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: SelfUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user = await user_service.update_user(
        db,
        current_user,
        UserUpdate(**payload.model_dump(exclude_unset=True)),
        current_user,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    permissions = await get_user_permission_codes(db, user.employee_id)
    user_out = to_user_out(user)
    return MeResponse(**user_out.model_dump(), permissions=sorted(permissions))


@router.post("/change-password", response_model=UserOut)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await auth_service.change_password(
        db,
        current_user,
        payload.current_password,
        payload.new_password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return to_user_out(user)
