from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_assignment import TaskAssignment
from app.models.user import User
from app.schemas.task_assignment import TaskAssignmentCreate, TaskAssignmentOut, TaskAssignmentUpdate
from app.services import task_service, user_service
from app.services.audit_service import AuditAction, create_audit_log

_TRACKED_FIELDS = ("assigned_date", "is_active")


def to_task_assignment_out(assignment: TaskAssignment) -> TaskAssignmentOut:
    return TaskAssignmentOut.model_validate(assignment)


def _snapshot(assignment: TaskAssignment) -> dict:
    snapshot = {field: getattr(assignment, field) for field in _TRACKED_FIELDS}
    if snapshot["assigned_date"] is not None:
        snapshot["assigned_date"] = snapshot["assigned_date"].isoformat()
    return snapshot


async def get_task_assignment_by_id(db: AsyncSession, task_assignment_id: str) -> TaskAssignment | None:
    result = await db.execute(
        select(TaskAssignment).where(TaskAssignment.task_assignment_id == task_assignment_id)
    )
    return result.scalar_one_or_none()


async def list_task_assignments(
    db: AsyncSession,
    *,
    task_id: str | None = None,
    project_id: str | None = None,
    employee_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[TaskAssignment], int]:
    query = select(TaskAssignment)
    count_query = select(func.count()).select_from(TaskAssignment)
    if task_id is not None:
        query = query.where(TaskAssignment.task_id == task_id)
        count_query = count_query.where(TaskAssignment.task_id == task_id)
    if project_id is not None:
        query = query.where(TaskAssignment.project_id == project_id)
        count_query = count_query.where(TaskAssignment.project_id == project_id)
    if employee_id is not None:
        query = query.where(TaskAssignment.employee_id == employee_id)
        count_query = count_query.where(TaskAssignment.employee_id == employee_id)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(TaskAssignment.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def _next_task_assignment_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(TaskAssignment))).scalar_one()
    return f"TA{total + 1:04d}"


async def create_task_assignment(
    db: AsyncSession,
    data: TaskAssignmentCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskAssignment:
    task = await task_service.get_task_by_id(db, data.task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if await user_service.get_user_by_id(db, data.employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    assignment = TaskAssignment(
        task_assignment_id=await _next_task_assignment_id(db),
        task_id=data.task_id,
        project_id=task.project_id,
        employee_id=data.employee_id,
        assigned_date=data.assigned_date,
        created_by=actor.employee_id,
    )
    db.add(assignment)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="task_assignment",
        entity_id=assignment.task_assignment_id,
        new_value=_snapshot(assignment)
        | {"task_id": assignment.task_id, "project_id": assignment.project_id, "employee_id": assignment.employee_id},
    )

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def update_task_assignment(
    db: AsyncSession,
    assignment: TaskAssignment,
    data: TaskAssignmentUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskAssignment:
    changes = data.model_dump(exclude_unset=True)

    old_values = _snapshot(assignment)

    for field, value in changes.items():
        setattr(assignment, field, value)

    if changes:
        assignment.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="task_assignment",
            entity_id=assignment.task_assignment_id,
            old_value=old_values,
            new_value=_snapshot(assignment),
        )

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def deactivate_task_assignment(
    db: AsyncSession,
    assignment: TaskAssignment,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskAssignment:
    if assignment.is_active:
        assignment.is_active = False
        assignment.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="task_assignment",
            entity_id=assignment.task_assignment_id,
            old_value={"is_active": True},
            new_value={"is_active": False},
        )
        await db.commit()
        await db.refresh(assignment)
    return assignment
