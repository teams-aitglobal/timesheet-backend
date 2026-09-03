from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.schemas.common import PaginatedResponse
from app.services import client_service

router = APIRouter(prefix="/clients", tags=["clients"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_client_or_404(db: AsyncSession, client_id: str) -> Client:
    client = await client_service.get_client_by_id(db, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientOut:
    client = await client_service.create_client(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_service.to_client_out(client)


@router.get("", response_model=PaginatedResponse[ClientOut])
async def list_clients(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("CLIENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ClientOut]:
    clients, total = await client_service.list_clients(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[client_service.to_client_out(c) for c in clients], total=total, skip=skip, limit=limit
    )


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: str,
    current_user: User = Depends(require_permission("CLIENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> ClientOut:
    client = await _get_client_or_404(db, client_id)
    return client_service.to_client_out(client)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: str,
    payload: ClientUpdate,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientOut:
    client = await _get_client_or_404(db, client_id)
    client = await client_service.update_client(
        db, client, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_service.to_client_out(client)


@router.delete("/{client_id}", response_model=ClientOut)
async def deactivate_client(
    client_id: str,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientOut:
    client = await _get_client_or_404(db, client_id)
    client = await client_service.deactivate_client(
        db, client, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_service.to_client_out(client)
