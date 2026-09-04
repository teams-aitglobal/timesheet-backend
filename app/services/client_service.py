from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.enums import ClientStatus
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services.audit_service import AuditAction, create_audit_log


def to_client_out(client: Client) -> ClientOut:
    return ClientOut.model_validate(client)


async def get_client_by_id(db: AsyncSession, client_id: str) -> Client | None:
    result = await db.execute(select(Client).where(Client.client_id == client_id))
    return result.scalar_one_or_none()


async def list_clients(db: AsyncSession, skip: int = 0, limit: int = 100) -> tuple[list[Client], int]:
    total = (await db.execute(select(func.count()).select_from(Client))).scalar_one()
    result = await db.execute(select(Client).order_by(Client.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def _next_client_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(Client))).scalar_one()
    return f"CLI{total + 1:04d}"


async def create_client(
    db: AsyncSession,
    data: ClientCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Client:
    client = Client(
        client_id=await _next_client_id(db),
        client_name=data.client_name,
        email=data.email,
        phone=data.phone,
        industry=data.industry,
        description=data.description,
        created_by=actor.employee_id,
    )
    db.add(client)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="client",
        entity_id=client.client_id,
        new_value={
            "client_name": client.client_name,
            "email": client.email,
            "phone": client.phone,
            "industry": client.industry,
        },
    )

    await db.commit()
    await db.refresh(client)
    return client


async def update_client(
    db: AsyncSession,
    client: Client,
    data: ClientUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Client:
    changes = data.model_dump(exclude_unset=True)

    old_values = {
        "client_name": client.client_name,
        "email": client.email,
        "phone": client.phone,
        "industry": client.industry,
        "description": client.description,
        "status": client.status,
    }

    for field, value in changes.items():
        setattr(client, field, value)

    if changes:
        client.updated_by = actor.employee_id
        new_values = {
            "client_name": client.client_name,
            "email": client.email,
            "phone": client.phone,
            "industry": client.industry,
            "description": client.description,
            "status": client.status,
        }
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="client",
            entity_id=client.client_id,
            old_value=old_values,
            new_value=new_values,
        )

    await db.commit()
    await db.refresh(client)
    return client


async def deactivate_client(
    db: AsyncSession,
    client: Client,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Client:
    if client.status != ClientStatus.INACTIVE:
        client.status = ClientStatus.INACTIVE
        client.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="client",
            entity_id=client.client_id,
            old_value={"status": ClientStatus.ACTIVE.value},
            new_value={"status": ClientStatus.INACTIVE.value},
        )
        await db.commit()
        await db.refresh(client)
    return client
