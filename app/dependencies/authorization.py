from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.permission_service import get_user_permission_codes


def require_permission(*required_codes: str) -> Callable:
    """Returns a FastAPI dependency that allows the request through only if the
    current user holds ALL of the given permission codes (via their roles).
    """

    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user_permissions = await get_user_permission_codes(db, current_user.employee_id)
        missing = set(required_codes) - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission(s): {', '.join(sorted(missing))}",
            )
        return current_user

    return dependency


def require_role(*allowed_role_names: str) -> Callable:
    """Returns a FastAPI dependency that allows the request through only if the
    current user holds at least one of the given role names.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {ur.role.name for ur in current_user.user_roles}
        if not user_role_names & set(allowed_role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of role(s): {', '.join(sorted(allowed_role_names))}",
            )
        return current_user

    return dependency
