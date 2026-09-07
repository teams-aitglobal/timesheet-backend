from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TimesheetStatus, WorkType
from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.role import SUPER_ADMIN
from app.models.task_assignment import TaskAssignment
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.timesheet import TimesheetCreate, TimesheetOut, TimesheetUpdate
from app.services import project_service, task_service
from app.services.audit_service import AuditAction, create_audit_log

_TRACKED_FIELDS = (
    "work_date",
    "project_id",
    "work_type",
    "task_id",
    "hours",
    "work_description",
    "employee_comment",
    "timesheet_status",
)

_EDITABLE_STATUSES = (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED)


def to_timesheet_out(timesheet: Timesheet) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet)


def _snapshot(timesheet: Timesheet) -> dict:
    snapshot = {field: getattr(timesheet, field) for field in _TRACKED_FIELDS}
    if snapshot["work_date"] is not None:
        snapshot["work_date"] = snapshot["work_date"].isoformat()
    if snapshot["work_type"] is not None:
        snapshot["work_type"] = snapshot["work_type"].value
    if snapshot["timesheet_status"] is not None:
        snapshot["timesheet_status"] = snapshot["timesheet_status"].value
    return snapshot


def _is_admin(user: User) -> bool:
    return any(ur.role.name == SUPER_ADMIN for ur in user.user_roles)


async def get_timesheet_by_id(db: AsyncSession, timesheet_id: str) -> Timesheet | None:
    result = await db.execute(select(Timesheet).where(Timesheet.timesheet_id == timesheet_id))
    return result.scalar_one_or_none()


async def _next_timesheet_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(Timesheet))).scalar_one()
    return f"TS{total + 1:04d}"


async def _assert_assigned_to_project(db: AsyncSession, employee_id: str, project_id: str) -> None:
    result = await db.execute(
        select(ProjectAssignment).where(
            ProjectAssignment.employee_id == employee_id,
            ProjectAssignment.project_id == project_id,
            ProjectAssignment.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this project."
        )


async def _assert_assigned_to_task(db: AsyncSession, employee_id: str, task_id: str) -> None:
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.employee_id == employee_id,
            TaskAssignment.task_id == task_id,
            TaskAssignment.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this task.")


async def _assert_daily_hours_within_limit(
    db: AsyncSession, employee_id: str, work_date: date, additional_hours: float, *, exclude_timesheet_id: str | None = None
) -> None:
    query = select(func.coalesce(func.sum(Timesheet.hours), 0)).where(
        Timesheet.employee_id == employee_id,
        Timesheet.work_date == work_date,
        Timesheet.timesheet_status != TimesheetStatus.REJECTED,
    )
    if exclude_timesheet_id is not None:
        query = query.where(Timesheet.timesheet_id != exclude_timesheet_id)
    existing_total = (await db.execute(query)).scalar_one()
    if float(existing_total) + additional_hours > 24:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Total logged hours for this date cannot exceed 24.",
        )


async def list_my_timesheets(
    db: AsyncSession,
    employee_id: str,
    *,
    project_id: str | None = None,
    timesheet_status: TimesheetStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Timesheet], int]:
    query = select(Timesheet).where(Timesheet.employee_id == employee_id)
    count_query = select(func.count()).select_from(Timesheet).where(Timesheet.employee_id == employee_id)
    if project_id is not None:
        query = query.where(Timesheet.project_id == project_id)
        count_query = count_query.where(Timesheet.project_id == project_id)
    if timesheet_status is not None:
        query = query.where(Timesheet.timesheet_status == timesheet_status)
        count_query = count_query.where(Timesheet.timesheet_status == timesheet_status)
    if date_from is not None:
        query = query.where(Timesheet.work_date >= date_from)
        count_query = count_query.where(Timesheet.work_date >= date_from)
    if date_to is not None:
        query = query.where(Timesheet.work_date <= date_to)
        count_query = count_query.where(Timesheet.work_date <= date_to)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Timesheet.work_date.desc()).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def list_timesheets(
    db: AsyncSession,
    requesting_user: User,
    *,
    employee_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    timesheet_status: TimesheetStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Timesheet], int]:
    query = select(Timesheet)
    count_query = select(func.count()).select_from(Timesheet)

    if not _is_admin(requesting_user):
        query = query.join(Project, Project.project_id == Timesheet.project_id).where(
            Project.project_manager_id == requesting_user.employee_id
        )
        count_query = count_query.join(Project, Project.project_id == Timesheet.project_id).where(
            Project.project_manager_id == requesting_user.employee_id
        )

    for column, value in (
        (Timesheet.employee_id, employee_id),
        (Timesheet.project_id, project_id),
        (Timesheet.task_id, task_id),
        (Timesheet.timesheet_status, timesheet_status),
    ):
        if value is not None:
            query = query.where(column == value)
            count_query = count_query.where(column == value)
    if date_from is not None:
        query = query.where(Timesheet.work_date >= date_from)
        count_query = count_query.where(Timesheet.work_date >= date_from)
    if date_to is not None:
        query = query.where(Timesheet.work_date <= date_to)
        count_query = count_query.where(Timesheet.work_date <= date_to)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Timesheet.work_date.desc()).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def list_pending_approval(
    db: AsyncSession, requesting_user: User, *, project_id: str | None = None, skip: int = 0, limit: int = 100
) -> tuple[list[Timesheet], int, float]:
    timesheets, total = await list_timesheets(
        db,
        requesting_user,
        project_id=project_id,
        timesheet_status=TimesheetStatus.SUBMITTED,
        skip=skip,
        limit=limit,
    )

    hours_query = select(func.coalesce(func.sum(Timesheet.hours), 0)).where(
        Timesheet.timesheet_status == TimesheetStatus.SUBMITTED
    )
    if not _is_admin(requesting_user):
        hours_query = hours_query.join(Project, Project.project_id == Timesheet.project_id).where(
            Project.project_manager_id == requesting_user.employee_id
        )
    if project_id is not None:
        hours_query = hours_query.where(Timesheet.project_id == project_id)
    total_hours = float((await db.execute(hours_query)).scalar_one())

    return timesheets, total, total_hours


async def sum_hours_by_project(
    db: AsyncSession,
    project_ids: list[str],
    *,
    status_filter: TimesheetStatus | None = TimesheetStatus.APPROVED,
) -> dict[str, float]:
    """Sums logged hours per project, e.g. for a "hours logged / budget" progress bar."""
    if not project_ids:
        return {}

    query = (
        select(Timesheet.project_id, func.coalesce(func.sum(Timesheet.hours), 0))
        .where(Timesheet.project_id.in_(project_ids))
        .group_by(Timesheet.project_id)
    )
    if status_filter is not None:
        query = query.where(Timesheet.timesheet_status == status_filter)

    result = await db.execute(query)
    return {project_id: float(hours) for project_id, hours in result.all()}


async def create_timesheet(db: AsyncSession, data: TimesheetCreate, actor: User) -> Timesheet:
    if data.work_date > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="work_date cannot be in the future.")

    project = await project_service.get_project_by_id(db, data.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    await _assert_assigned_to_project(db, actor.employee_id, data.project_id)

    if data.work_type == WorkType.ASSIGNED_TASK:
        task = await task_service.get_task_by_id(db, data.task_id)
        if task is None or task.project_id != data.project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found on this project.")
        await _assert_assigned_to_task(db, actor.employee_id, data.task_id)

    await _assert_daily_hours_within_limit(db, actor.employee_id, data.work_date, data.hours)

    timesheet = Timesheet(
        timesheet_id=await _next_timesheet_id(db),
        employee_id=actor.employee_id,
        work_date=data.work_date,
        project_id=data.project_id,
        work_type=data.work_type,
        task_id=data.task_id,
        hours=data.hours,
        work_description=data.work_description,
        employee_comment=data.employee_comment,
        timesheet_status=TimesheetStatus.DRAFT,
    )
    db.add(timesheet)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        new_value=_snapshot(timesheet),
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


def _assert_owner_and_editable(timesheet: Timesheet, actor: User) -> None:
    if timesheet.employee_id != actor.employee_id and not _is_admin(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this timesheet entry.")
    if timesheet.timesheet_status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot modify a timesheet in {timesheet.timesheet_status.value} status.",
        )


async def update_timesheet(db: AsyncSession, timesheet: Timesheet, data: TimesheetUpdate, actor: User) -> Timesheet:
    _assert_owner_and_editable(timesheet, actor)

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return timesheet

    new_project_id = changes.get("project_id", timesheet.project_id)
    new_work_type = changes.get("work_type", timesheet.work_type)
    new_task_id = changes.get("task_id", timesheet.task_id)
    new_work_date = changes.get("work_date", timesheet.work_date)
    new_hours = changes.get("hours", timesheet.hours)

    if new_work_date > date.today():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="work_date cannot be in the future.")

    if new_work_type == WorkType.ASSIGNED_TASK:
        if new_task_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="task_id is required when work_type is Assigned Task.",
            )
        task = await task_service.get_task_by_id(db, new_task_id)
        if task is None or task.project_id != new_project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found on this project.")
        await _assert_assigned_to_task(db, timesheet.employee_id, new_task_id)
    elif new_task_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="task_id must be omitted unless work_type is Assigned Task.",
        )

    if new_project_id != timesheet.project_id:
        project = await project_service.get_project_by_id(db, new_project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        await _assert_assigned_to_project(db, timesheet.employee_id, new_project_id)

    if "hours" in changes or "work_date" in changes:
        await _assert_daily_hours_within_limit(
            db, timesheet.employee_id, new_work_date, new_hours, exclude_timesheet_id=timesheet.timesheet_id
        )

    old_values = _snapshot(timesheet)
    for field, value in changes.items():
        setattr(timesheet, field, value)

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value=old_values,
        new_value=_snapshot(timesheet),
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


async def delete_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User) -> None:
    _assert_owner_and_editable(timesheet, actor)

    await create_audit_log(
        db,
        action=AuditAction.DELETED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value=_snapshot(timesheet),
    )
    await db.delete(timesheet)
    await db.commit()


async def submit_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User) -> Timesheet:
    if timesheet.employee_id != actor.employee_id and not _is_admin(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this timesheet entry.")
    if timesheet.timesheet_status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot submit a timesheet in {timesheet.timesheet_status.value} status.",
        )

    old_status = timesheet.timesheet_status
    timesheet.timesheet_status = TimesheetStatus.SUBMITTED
    timesheet.submitted_at = datetime.now(timezone.utc)
    timesheet.rejection_reason = None

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": old_status.value},
        new_value={"timesheet_status": TimesheetStatus.SUBMITTED.value, "submitted_at": timesheet.submitted_at.isoformat()},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


def _assert_can_review(timesheet: Timesheet, project: Project, actor: User) -> None:
    if not _is_admin(actor) and project.project_manager_id != actor.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage the project for this timesheet entry."
        )
    if timesheet.timesheet_status != TimesheetStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot review a timesheet in {timesheet.timesheet_status.value} status.",
        )


async def approve_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User) -> Timesheet:
    project = await project_service.get_project_by_id(db, timesheet.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    _assert_can_review(timesheet, project, actor)

    timesheet.timesheet_status = TimesheetStatus.APPROVED
    timesheet.approved_at = datetime.now(timezone.utc)
    timesheet.approved_by = actor.employee_id

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": TimesheetStatus.SUBMITTED.value},
        new_value={"timesheet_status": TimesheetStatus.APPROVED.value, "approved_by": actor.employee_id},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


async def reject_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User, rejection_reason: str) -> Timesheet:
    project = await project_service.get_project_by_id(db, timesheet.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    _assert_can_review(timesheet, project, actor)

    timesheet.timesheet_status = TimesheetStatus.REJECTED
    timesheet.rejection_reason = rejection_reason

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": TimesheetStatus.SUBMITTED.value},
        new_value={"timesheet_status": TimesheetStatus.REJECTED.value, "rejection_reason": rejection_reason},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet
