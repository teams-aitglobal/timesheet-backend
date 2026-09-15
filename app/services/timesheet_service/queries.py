from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TimesheetStatus
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.models.user import User

from .common import _is_admin


async def get_timesheet_by_id(db: AsyncSession, timesheet_id: str) -> Timesheet | None:
    result = await db.execute(select(Timesheet).where(Timesheet.timesheet_id == timesheet_id))
    return result.scalar_one_or_none()


async def list_my_timesheets(
    db: AsyncSession,
    employee_id: str,
    *,
    project_id: str | None = None,
    client_id: str | None = None,
    timesheet_status: TimesheetStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Timesheet], int]:
    query = select(Timesheet).where(Timesheet.employee_id == employee_id)
    count_query = select(func.count()).select_from(Timesheet).where(Timesheet.employee_id == employee_id)
    if client_id is not None:
        query = query.join(Project, Project.project_id == Timesheet.project_id).where(Project.client_id == client_id)
        count_query = count_query.join(Project, Project.project_id == Timesheet.project_id).where(
            Project.client_id == client_id
        )
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
    client_id: str | None = None,
    task_id: str | None = None,
    timesheet_status: TimesheetStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Timesheet], int]:
    query = select(Timesheet)
    count_query = select(func.count()).select_from(Timesheet)

    if not _is_admin(requesting_user) or client_id is not None:
        query = query.join(Project, Project.project_id == Timesheet.project_id)
        count_query = count_query.join(Project, Project.project_id == Timesheet.project_id)
        if not _is_admin(requesting_user):
            query = query.where(Project.project_manager_id == requesting_user.employee_id)
            count_query = count_query.where(Project.project_manager_id == requesting_user.employee_id)
        if client_id is not None:
            query = query.where(Project.client_id == client_id)
            count_query = count_query.where(Project.client_id == client_id)

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


async def sum_hours_by_task(
    db: AsyncSession,
    task_ids: list[str],
    *,
    status_filter: TimesheetStatus | None = TimesheetStatus.APPROVED,
) -> dict[str, float]:
    """Sums logged hours per task, e.g. for a "planned vs. logged" progress bar."""
    if not task_ids:
        return {}

    query = (
        select(Timesheet.task_id, func.coalesce(func.sum(Timesheet.hours), 0))
        .where(Timesheet.task_id.in_(task_ids))
        .group_by(Timesheet.task_id)
    )
    if status_filter is not None:
        query = query.where(Timesheet.timesheet_status == status_filter)

    result = await db.execute(query)
    return {task_id: float(hours) for task_id, hours in result.all()}
