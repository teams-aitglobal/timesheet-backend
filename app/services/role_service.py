import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import SUPER_ADMIN, Role
from app.models.user import User
from app.models.user_role import UserRole


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).where(Role.is_active.is_(True)).order_by(Role.name))
    return list(result.scalars().all())


async def get_roles_by_ids(db: AsyncSession, role_ids: list[uuid.UUID]) -> list[Role]:
    result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
    return list(result.scalars().all())


async def get_user_roles(db: AsyncSession, user_id: str) -> list[Role]:
    result = await db.execute(
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())


def assert_can_assign_roles(actor: User, actor_role_names: set[str], roles: list[Role]) -> None:
    """Only a SUPER_ADMIN may grant the SUPER_ADMIN role. Everyone else attempting
    to hand out SUPER_ADMIN is rejected, even if they otherwise hold USER_ROLE_ASSIGN.
    """
    if any(role.name == SUPER_ADMIN for role in roles) and SUPER_ADMIN not in actor_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a SUPER_ADMIN may assign the SUPER_ADMIN role.",
        )


def assert_can_remove_role(actor_role_names: set[str], role: Role) -> None:
    """Mirrors assert_can_assign_roles: only a SUPER_ADMIN may strip the
    SUPER_ADMIN role from someone.
    """
    if role.name == SUPER_ADMIN and SUPER_ADMIN not in actor_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a SUPER_ADMIN may remove the SUPER_ADMIN role.",
        )


async def assign_roles_to_user(db: AsyncSession, user: User, roles: list[Role]) -> list[UserRole]:
    existing = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user.employee_id))
    existing_role_ids = set(existing.scalars().all())

    created: list[UserRole] = []
    for role in roles:
        if role.id in existing_role_ids:
            continue
        user_role = UserRole(user_id=user.employee_id, role_id=role.id)
        db.add(user_role)
        created.append(user_role)

    await db.flush()
    return created


async def remove_role_from_user(db: AsyncSession, user_id: str, role_id: uuid.UUID) -> UserRole | None:
    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    user_role = result.scalar_one_or_none()
    if user_role is None:
        return None
    await db.delete(user_role)
    await db.flush()
    return user_role
