from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.task import Task
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _get_task_or_404(db: AsyncSession, task_id: str) -> Task:
    task = await task_service.get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    request: Request,
    current_user: User = Depends(require_permission("TASK_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    task = await task_service.create_task(
        db, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_service.to_task_out(task)


@router.get("", response_model=PaginatedResponse[TaskOut])
async def list_tasks(
    project_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("TASK_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TaskOut]:
    tasks, total = await task_service.list_tasks(
        db, project_id=project_id, status_filter=status_filter, search=search, skip=skip, limit=limit
    )
    return PaginatedResponse(items=[task_service.to_task_out(t) for t in tasks], total=total, skip=skip, limit=limit)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    current_user: User = Depends(require_permission("TASK_READ")),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    task = await _get_task_or_404(db, task_id)
    return task_service.to_task_out(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    request: Request,
    current_user: User = Depends(require_permission("TASK_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    task = await _get_task_or_404(db, task_id)
    task = await task_service.update_task(
        db, task, payload, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_service.to_task_out(task)


@router.delete("/{task_id}", response_model=TaskOut)
async def cancel_task(
    task_id: str,
    request: Request,
    current_user: User = Depends(require_permission("TASK_CANCEL")),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    task = await _get_task_or_404(db, task_id)
    task = await task_service.cancel_task(
        db, task, current_user, ip_address=_client_ip(request), user_agent=_user_agent(request)
    )
    return task_service.to_task_out(task)
