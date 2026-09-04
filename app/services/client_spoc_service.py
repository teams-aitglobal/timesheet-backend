from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_spoc import ClientSpoc
from app.models.enums import ClientSpocStatus
from app.models.user import User
from app.schemas.client_spoc import ClientSpocCreate, ClientSpocOut, ClientSpocUpdate
from app.services import client_service
from app.services.audit_service import AuditAction, create_audit_log


def to_client_spoc_out(spoc: ClientSpoc) -> ClientSpocOut:
    return ClientSpocOut.model_validate(spoc)


async def get_client_spoc_by_id(db: AsyncSession, client_spoc_id: str) -> ClientSpoc | None:
    result = await db.execute(select(ClientSpoc).where(ClientSpoc.client_spoc_id == client_spoc_id))
    return result.scalar_one_or_none()


async def _get_by_client_and_email(
    db: AsyncSession, client_id: str, email: str, *, except_id: str | None = None
) -> ClientSpoc | None:
    stmt = select(ClientSpoc).where(ClientSpoc.client_id == client_id, ClientSpoc.email == email)
    if except_id is not None:
        stmt = stmt.where(ClientSpoc.client_spoc_id != except_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_client_spocs(
    db: AsyncSession, *, client_id: str | None = None, skip: int = 0, limit: int = 100
) -> tuple[list[ClientSpoc], int]:
    query = select(ClientSpoc)
    count_query = select(func.count()).select_from(ClientSpoc)
    if client_id is not None:
        query = query.where(ClientSpoc.client_id == client_id)
        count_query = count_query.where(ClientSpoc.client_id == client_id)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(ClientSpoc.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def _next_client_spoc_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(ClientSpoc))).scalar_one()
    return f"SPOC{total + 1:04d}"


async def _unset_other_primaries(db: AsyncSession, client_id: str, *, except_id: str | None = None) -> None:
    stmt = update(ClientSpoc).where(ClientSpoc.client_id == client_id, ClientSpoc.is_primary.is_(True))
    if except_id is not None:
        stmt = stmt.where(ClientSpoc.client_spoc_id != except_id)
    await db.execute(stmt.values(is_primary=False))


async def create_client_spoc(
    db: AsyncSession,
    data: ClientSpocCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ClientSpoc:
    if await client_service.get_client_by_id(db, data.client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    if await _get_by_client_and_email(db, data.client_id, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This client already has a SPOC with this email."
        )

    spoc = ClientSpoc(
        client_spoc_id=await _next_client_spoc_id(db),
        client_id=data.client_id,
        client_spoc_name=data.client_spoc_name,
        email=data.email,
        phone=data.phone,
        designation=data.designation,
        is_primary=data.is_primary,
        created_by=actor.employee_id,
    )
    db.add(spoc)

    if data.is_primary:
        await _unset_other_primaries(db, data.client_id, except_id=spoc.client_spoc_id)

    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="client_spoc",
        entity_id=spoc.client_spoc_id,
        new_value={
            "client_id": spoc.client_id,
            "client_spoc_name": spoc.client_spoc_name,
            "email": spoc.email,
            "phone": spoc.phone,
            "designation": spoc.designation,
            "is_primary": spoc.is_primary,
        },
    )

    await db.commit()
    await db.refresh(spoc)
    return spoc


async def update_client_spoc(
    db: AsyncSession,
    spoc: ClientSpoc,
    data: ClientSpocUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ClientSpoc:
    changes = data.model_dump(exclude_unset=True)

    new_email = changes.get("email")
    if new_email is not None and new_email != spoc.email:
        if await _get_by_client_and_email(db, spoc.client_id, new_email, except_id=spoc.client_spoc_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="This client already has a SPOC with this email."
            )

    old_values = {
        "client_spoc_name": spoc.client_spoc_name,
        "email": spoc.email,
        "phone": spoc.phone,
        "designation": spoc.designation,
        "is_primary": spoc.is_primary,
        "status": spoc.status,
    }

    for field, value in changes.items():
        setattr(spoc, field, value)

    if changes.get("is_primary") is True:
        await _unset_other_primaries(db, spoc.client_id, except_id=spoc.client_spoc_id)

    if changes:
        spoc.updated_by = actor.employee_id
        new_values = {
            "client_spoc_name": spoc.client_spoc_name,
            "email": spoc.email,
            "phone": spoc.phone,
            "designation": spoc.designation,
            "is_primary": spoc.is_primary,
            "status": spoc.status,
        }
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="client_spoc",
            entity_id=spoc.client_spoc_id,
            old_value=old_values,
            new_value=new_values,
        )

    await db.commit()
    await db.refresh(spoc)
    return spoc


async def deactivate_client_spoc(
    db: AsyncSession,
    spoc: ClientSpoc,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ClientSpoc:
    if spoc.status != ClientSpocStatus.INACTIVE:
        spoc.status = ClientSpocStatus.INACTIVE
        spoc.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="client_spoc",
            entity_id=spoc.client_spoc_id,
            old_value={"status": ClientSpocStatus.ACTIVE.value},
            new_value={"status": ClientSpocStatus.INACTIVE.value},
        )
        await db.commit()
        await db.refresh(spoc)
    return spoc
