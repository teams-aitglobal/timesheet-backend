from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.client_spoc import ClientSpoc
from app.models.user import User
from app.schemas.client_spoc import ClientSpocCreate, ClientSpocOut, ClientSpocUpdate
from app.schemas.common import PaginatedResponse
from app.services import client_spoc_service

router = APIRouter(prefix="/client-spocs", tags=["client-spocs"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_client_spoc_or_404(db: AsyncSession, client_spoc_id: str) -> ClientSpoc:
    spoc = await client_spoc_service.get_client_spoc_by_id(db, client_spoc_id)
    if spoc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client SPOC not found.")
    return spoc


@router.post("", response_model=ClientSpocOut, status_code=status.HTTP_201_CREATED)
async def create_client_spoc(
    payload: ClientSpocCreate,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_SPOC_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientSpocOut:
    spoc = await client_spoc_service.create_client_spoc(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_spoc_service.to_client_spoc_out(spoc)


@router.get("", response_model=PaginatedResponse[ClientSpocOut])
async def list_client_spocs(
    client_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("CLIENT_SPOC_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ClientSpocOut]:
    spocs, total = await client_spoc_service.list_client_spocs(db, client_id=client_id, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[client_spoc_service.to_client_spoc_out(s) for s in spocs], total=total, skip=skip, limit=limit
    )


@router.get("/{client_spoc_id}", response_model=ClientSpocOut)
async def get_client_spoc(
    client_spoc_id: str,
    current_user: User = Depends(require_permission("CLIENT_SPOC_READ")),
    db: AsyncSession = Depends(get_db),
) -> ClientSpocOut:
    spoc = await _get_client_spoc_or_404(db, client_spoc_id)
    return client_spoc_service.to_client_spoc_out(spoc)


@router.patch("/{client_spoc_id}", response_model=ClientSpocOut)
async def update_client_spoc(
    client_spoc_id: str,
    payload: ClientSpocUpdate,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_SPOC_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientSpocOut:
    spoc = await _get_client_spoc_or_404(db, client_spoc_id)
    spoc = await client_spoc_service.update_client_spoc(
        db, spoc, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_spoc_service.to_client_spoc_out(spoc)


@router.delete("/{client_spoc_id}", response_model=ClientSpocOut)
async def deactivate_client_spoc(
    client_spoc_id: str,
    request: Request,
    current_user: User = Depends(require_permission("CLIENT_SPOC_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> ClientSpocOut:
    spoc = await _get_client_spoc_or_404(db, client_spoc_id)
    spoc = await client_spoc_service.deactivate_client_spoc(
        db, spoc, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return client_spoc_service.to_client_spoc_out(spoc)
