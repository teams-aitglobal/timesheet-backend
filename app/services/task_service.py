from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.schemas.task import MyTaskOut, TaskCreate, TaskOut, TaskUpdate
from app.services import project_service
from app.services.audit_service import AuditAction, create_audit_log

_TRACKED_FIELDS = (
    "task_name",
    "task_description",
    "planned_hours",
    "start_date",
    "due_date",
    "status",
)


def to_task_out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task)


def _snapshot(task: Task) -> dict:
    snapshot = {field: getattr(task, field) for field in _TRACKED_FIELDS}
    for date_field in ("start_date", "due_date"):
        if snapshot[date_field] is not None:
            snapshot[date_field] = snapshot[date_field].isoformat()
    return snapshot


async def get_task_by_id(db: AsyncSession, task_id: str) -> Task | None:
    result = await db.execute(select(Task).where(Task.task_id == task_id))
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    status_filter: TaskStatus | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Task], int]:
    query = select(Task)
    count_query = select(func.count()).select_from(Task)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
        count_query = count_query.where(Task.project_id == project_id)
    if status_filter is not None:
        query = query.where(Task.status == status_filter)
        count_query = count_query.where(Task.status == status_filter)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(Task.task_name.ilike(pattern))
        count_query = count_query.where(Task.task_name.ilike(pattern))

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Task.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def list_my_tasks(
    db: AsyncSession, employee_id: str, project_id: str | None = None
) -> list[MyTaskOut]:
    query = (
        select(Task, TaskAssignment)
        .join(TaskAssignment, TaskAssignment.task_id == Task.task_id)
        .where(TaskAssignment.employee_id == employee_id, TaskAssignment.is_active.is_(True))
        .order_by(Task.start_date.desc())
    )
    if project_id is not None:
        query = query.where(Task.project_id == project_id)

    result = await db.execute(query)
    return [
        MyTaskOut(
            task_id=task.task_id,
            project_id=task.project_id,
            task_assignment_id=assignment.task_assignment_id,
            task_name=task.task_name,
            task_description=task.task_description,
            planned_hours=task.planned_hours,
            start_date=task.start_date,
            due_date=task.due_date,
            status=task.status,
        )
        for task, assignment in result.all()
    ]


async def update_my_task_status(
    db: AsyncSession,
    task_id: str,
    employee_id: str,
    new_status: TaskStatus,
    actor: User,
) -> Task:
    task = await get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    assignment_result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.employee_id == employee_id,
            TaskAssignment.is_active.is_(True),
        )
    )
    if assignment_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this task."
        )

    return await update_task(db, task, TaskUpdate(status=new_status), actor)


async def _next_task_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    return f"TSK{total + 1:04d}"


async def create_task(
    db: AsyncSession,
    data: TaskCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Task:
    if await project_service.get_project_by_id(db, data.project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    task = Task(
        task_id=await _next_task_id(db),
        project_id=data.project_id,
        task_name=data.task_name,
        task_description=data.task_description,
        planned_hours=data.planned_hours,
        start_date=data.start_date,
        due_date=data.due_date,
        created_by=actor.employee_id,
    )
    db.add(task)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="task",
        entity_id=task.task_id,
        new_value=_snapshot(task) | {"project_id": task.project_id},
    )

    await db.commit()
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession,
    task: Task,
    data: TaskUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Task:
    changes = data.model_dump(exclude_unset=True)

    new_start = changes.get("start_date", task.start_date)
    new_due = changes.get("due_date", task.due_date)
    if new_due is not None and new_due < new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date cannot be before start_date.",
        )

    old_values = _snapshot(task)

    for field, value in changes.items():
        setattr(task, field, value)

    if changes:
        task.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="task",
            entity_id=task.task_id,
            old_value=old_values,
            new_value=_snapshot(task),
        )

    await db.commit()
    await db.refresh(task)
    return task


async def cancel_task(
    db: AsyncSession,
    task: Task,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Task:
    if task.status != TaskStatus.CANCELLED:
        old_status = task.status
        task.status = TaskStatus.CANCELLED
        task.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="task",
            entity_id=task.task_id,
            old_value={"status": old_status.value},
            new_value={"status": TaskStatus.CANCELLED.value},
        )
        await db.commit()
        await db.refresh(task)
    return task
