from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task_assignment import (
    TaskAssignmentCreate,
    TaskAssignmentOut,
    TaskAssignmentUpdate,
)
from app.services import task_assignment_service

router = APIRouter(prefix="/task-assignments", tags=["task-assignments"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_task_assignment_or_404(db: AsyncSession, task_assignment_id: str) -> TaskAssignment:
    assignment = await task_assignment_service.get_task_assignment_by_id(db, task_assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task assignment not found.")
    return assignment


@router.post("", response_model=TaskAssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_task_assignment(
    payload: TaskAssignmentCreate,
    request: Request,
    current_user: User = Depends(require_permission("TASK_ASSIGN_EMPLOYEE")),
    db: AsyncSession = Depends(get_db),
) -> TaskAssignmentOut:
    assignment = await task_assignment_service.create_task_assignment(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_assignment_service.to_task_assignment_out(assignment)


@router.get("", response_model=PaginatedResponse[TaskAssignmentOut])
async def list_task_assignments(
    task_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("TASK_ASSIGNMENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TaskAssignmentOut]:
    assignments, total = await task_assignment_service.list_task_assignments(
        db, task_id=task_id, project_id=project_id, employee_id=employee_id, skip=skip, limit=limit
    )
    return PaginatedResponse(
        items=[task_assignment_service.to_task_assignment_out(a) for a in assignments],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{task_assignment_id}", response_model=TaskAssignmentOut)
async def get_task_assignment(
    task_assignment_id: str,
    current_user: User = Depends(require_permission("TASK_ASSIGNMENT_READ")),
    db: AsyncSession = Depends(get_db),
) -> TaskAssignmentOut:
    assignment = await _get_task_assignment_or_404(db, task_assignment_id)
    return task_assignment_service.to_task_assignment_out(assignment)


@router.patch("/{task_assignment_id}", response_model=TaskAssignmentOut)
async def update_task_assignment(
    task_assignment_id: str,
    payload: TaskAssignmentUpdate,
    request: Request,
    current_user: User = Depends(require_permission("TASK_ASSIGNMENT_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> TaskAssignmentOut:
    assignment = await _get_task_assignment_or_404(db, task_assignment_id)
    assignment = await task_assignment_service.update_task_assignment(
        db, assignment, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_assignment_service.to_task_assignment_out(assignment)


@router.delete("/{task_assignment_id}", response_model=TaskAssignmentOut)
async def deactivate_task_assignment(
    task_assignment_id: str,
    request: Request,
    current_user: User = Depends(require_permission("TASK_ASSIGNMENT_DEACTIVATE")),
    db: AsyncSession = Depends(get_db),
) -> TaskAssignmentOut:
    assignment = await _get_task_assignment_or_404(db, task_assignment_id)
    assignment = await task_assignment_service.deactivate_task_assignment(
        db, assignment, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_assignment_service.to_task_assignment_out(assignment)
