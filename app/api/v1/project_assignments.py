from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.project_assignment import ProjectAssignment
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.project_assignment import (
    ProjectAssignmentCreate,
    ProjectAssignmentOut,
    ProjectAssignmentUpdate,
)
from app.services import project_assignment_service

router = APIRouter(prefix="/project-assignments", tags=["project-assignments"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_project_assignment_or_404(db: AsyncSession, project_assignment_id: str) -> ProjectAssignment:
    assignment = await project_assignment_service.get_project_assignment_by_id(db, project_assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project assignment not found.")
    return assignment


@router.post("", response_model=ProjectAssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_project_assignment(
    payload: ProjectAssignmentCreate,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_ASSIGN_EMPLOYEE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectAssignmentOut:
    assignment = await project_assignment_service.create_project_assignment(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_assignment_service.to_project_assignment_out(assignment)


@router.get("", response_model=PaginatedResponse[ProjectAssignmentOut])
async def list_project_assignments(
    project_id: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("PROJECT_ASSIGNMENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProjectAssignmentOut]:
    assignments, total = await project_assignment_service.list_project_assignments(
        db, project_id=project_id, employee_id=employee_id, skip=skip, limit=limit
    )
    return PaginatedResponse(
        items=[project_assignment_service.to_project_assignment_out(a) for a in assignments],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{project_assignment_id}", response_model=ProjectAssignmentOut)
async def get_project_assignment(
    project_assignment_id: str,
    current_user: User = Depends(require_permission("PROJECT_ASSIGNMENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> ProjectAssignmentOut:
    assignment = await _get_project_assignment_or_404(db, project_assignment_id)
    return project_assignment_service.to_project_assignment_out(assignment)


@router.patch("/{project_assignment_id}", response_model=ProjectAssignmentOut)
async def update_project_assignment(
    project_assignment_id: str,
    payload: ProjectAssignmentUpdate,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_ASSIGNMENT_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectAssignmentOut:
    assignment = await _get_project_assignment_or_404(db, project_assignment_id)
    assignment = await project_assignment_service.update_project_assignment(
        db, assignment, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_assignment_service.to_project_assignment_out(assignment)


@router.delete("/{project_assignment_id}", response_model=ProjectAssignmentOut)
async def deactivate_project_assignment(
    project_assignment_id: str,
    request: Request,
    current_user: User = Depends(require_permission("PROJECT_ASSIGNMENT_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> ProjectAssignmentOut:
    assignment = await _get_project_assignment_or_404(db, project_assignment_id)
    assignment = await project_assignment_service.deactivate_project_assignment(
        db, assignment, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return project_assignment_service.to_project_assignment_out(assignment)
