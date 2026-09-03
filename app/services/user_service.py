import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_temporary_password, hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import role_service
from app.services.audit_service import AuditAction, create_audit_log


def user_role_names(user: User) -> set[str]:
    return {ur.role.name for ur in user.user_roles}


def to_user_out(user: User) -> UserOut:
    return UserOut(
        employee_id=user.employee_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        designation_id=user.designation_id,
        date_of_joining=user.date_of_joining,
        description=user.description,
        status=user.status,
        is_verified=user.is_verified,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        created_by=user.created_by,
        updated_at=user.updated_at,
        updated_by=user.updated_by,
        roles=sorted(user_role_names(user)),
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, employee_id: str) -> User | None:
    result = await db.execute(select(User).where(User.employee_id == employee_id))
    return result.scalar_one_or_none()


async def next_employee_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    return f"EMP{total + 1:04d}"


async def _reload_user(db: AsyncSession, employee_id: str) -> User:
    """Re-fetches a user after a mutation that touched their roles within this
    same session (e.g. a new UserRole row). A plain select() would return the
    same Python object from the session's identity map with its already-loaded
    user_roles collection left stale, since SQLAlchemy does not refresh
    previously-loaded relationships on a repeat query by default.
    populate_existing=True forces it to re-populate from the fresh row data,
    correctly re-running the User.user_roles -> UserRole.role selectin chain.
    """
    result = await db.execute(
        select(User).where(User.employee_id == employee_id).execution_options(populate_existing=True)
    )
    user = result.scalar_one_or_none()
    assert user is not None
    return user


async def list_users(
    db: AsyncSession, skip: int = 0, limit: int = 100, search: str | None = None
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if search:
        pattern = f"%{search.strip()}%"
        condition = or_(
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            User.email.ilike(pattern),
        )
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(User.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def create_user(
    db: AsyncSession,
    data: UserCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    if await get_user_by_email(db, data.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    roles = await role_service.get_roles_by_ids(db, data.role_ids)
    if len(roles) != len(set(data.role_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more role_ids are invalid.")

    role_service.assert_can_assign_roles(actor, user_role_names(actor), roles)

    temporary_password = generate_temporary_password()
    user = User(
        employee_id=await next_employee_id(db),
        email=data.email,
        password_hash=hash_password(temporary_password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        designation_id=data.designation_id,
        date_of_joining=data.date_of_joining,
        description=data.description,
        must_change_password=True,
        created_by=actor.employee_id,
    )
    db.add(user)
    await db.flush()

    await role_service.assign_roles_to_user(db, user, roles)

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="user",
        entity_id=user.employee_id,
        new_value={"email": user.email, "first_name": user.first_name, "last_name": user.last_name},
    )
    await create_audit_log(
        db,
        action=AuditAction.ROLE_ASSIGNED,
        changed_by=actor.employee_id,
        entity_type="user",
        entity_id=user.employee_id,
        new_value={"roles": [role.name for role in roles]},
    )

    await db.commit()
    user = await _reload_user(db, user.employee_id)
    return user, temporary_password


async def update_user(
    db: AsyncSession,
    user: User,
    data: UserUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    old_values = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "designation_id": user.designation_id,
        "date_of_joining": str(user.date_of_joining) if user.date_of_joining else None,
        "description": user.description,
        "status": user.status,
    }
    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(user, field, value)

    if changes:
        user.updated_by = actor.employee_id
        new_values = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "designation_id": user.designation_id,
            "date_of_joining": str(user.date_of_joining) if user.date_of_joining else None,
            "description": user.description,
            "status": user.status,
        }
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            old_value=old_values,
            new_value=new_values,
        )

    await db.commit()
    user = await _reload_user(db, user.employee_id)
    return user


async def deactivate_user(
    db: AsyncSession,
    user: User,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    if user.status != "Inactive":
        user.status = "Inactive"
        user.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            old_value={"status": "Active"},
            new_value={"status": "Inactive"},
        )
        await db.commit()
        await db.refresh(user)
    return user


async def assign_roles(
    db: AsyncSession,
    user: User,
    role_ids: list[uuid.UUID],
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    roles = await role_service.get_roles_by_ids(db, role_ids)
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more role_ids are invalid.")

    role_service.assert_can_assign_roles(actor, user_role_names(actor), roles)

    created = await role_service.assign_roles_to_user(db, user, roles)
    if created:
        await create_audit_log(
            db,
            action=AuditAction.ROLE_ASSIGNED,
            changed_by=actor.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"roles": [r.name for r in roles if r.id in {c.role_id for c in created}]},
        )
        await db.commit()
        user = await _reload_user(db, user.employee_id)
    return user


async def remove_role(
    db: AsyncSession,
    user: User,
    role_id: uuid.UUID,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    roles = await role_service.get_roles_by_ids(db, [role_id])
    if not roles:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    role = roles[0]

    current_role_names = user_role_names(user)
    if role.name not in current_role_names:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not hold this role.")
    if len(current_role_names) == 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove a user's only role.")

    role_service.assert_can_remove_role(user_role_names(actor), role)

    removed = await role_service.remove_role_from_user(db, user.employee_id, role_id)
    if removed is not None:
        await create_audit_log(
            db,
            action=AuditAction.ROLE_REMOVED,
            changed_by=actor.employee_id,
            entity_type="user",
            entity_id=user.employee_id,
            new_value={"roles": [role.name]},
        )
        await db.commit()
        user = await _reload_user(db, user.employee_id)
    return user
