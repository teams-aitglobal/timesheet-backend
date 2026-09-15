from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_project_or_404(db: AsyncSession, project_id: str) -> Project:
    project = await project_service.get_project_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.create_project(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_service.to_project_out(project)


@router.get("", response_model=PaginatedResponse[ProjectOut])
async def list_projects(
    client_id: str | None = Query(default=None),
    project_manager_id: str | None = Query(default=None),
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("PROJECT_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProjectOut]:
    projects, total = await project_service.list_projects(
        db,
        client_id=client_id,
        project_manager_id=project_manager_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(
        items=[project_service.to_project_out(p) for p in projects], total=total, skip=skip, limit=limit
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(require_permission("PROJECT_READ")),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_project_or_404(db, project_id)
    return project_service.to_project_out(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_project_or_404(db, project_id)
    project = await project_service.update_project(
        db, project, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_service.to_project_out(project)


@router.delete("/{project_id}", response_model=ProjectOut)
async def deactivate_project(
    project_id: str,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await _get_project_or_404(db, project_id)
    project = await project_service.deactivate_project(
        db, project, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_service.to_project_out(project)
