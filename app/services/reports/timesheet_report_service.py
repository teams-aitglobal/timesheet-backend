from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TimesheetStatus
from app.models.role import PROJECT_MANAGER, SUPER_ADMIN
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.reports import TimesheetReportRow
from app.services import lookups, timesheet_service


def _is_manager_or_admin(user: User) -> bool:
    role_names = {ur.role.name for ur in user.user_roles}
    return bool(role_names & {SUPER_ADMIN, PROJECT_MANAGER})


async def _to_rows(db: AsyncSession, timesheets: list[Timesheet]) -> list[TimesheetReportRow]:
    employee_names = await lookups.employee_names_by_id(db, {t.employee_id for t in timesheets})
    project_names = await lookups.project_names_by_id(db, {t.project_id for t in timesheets})
    project_client_ids = await lookups.project_client_ids_by_id(db, {t.project_id for t in timesheets})
    client_names = await lookups.client_names_by_id(db, set(project_client_ids.values()))
    task_names = await lookups.task_names_by_id(db, {t.task_id for t in timesheets if t.task_id})
    return [
        TimesheetReportRow(
            timesheet_id=t.timesheet_id,
            employee_id=t.employee_id,
            employee_name=employee_names.get(t.employee_id, t.employee_id),
            work_date=t.work_date,
            project_id=t.project_id,
            project_name=project_names.get(t.project_id, t.project_id),
            client_id=project_client_ids.get(t.project_id, ""),
            client_name=client_names.get(project_client_ids.get(t.project_id, ""), ""),
            work_type=t.work_type,
            task_id=t.task_id,
            task_name=task_names.get(t.task_id) if t.task_id else None,
            hours=t.hours,
            work_description=t.work_description,
            timesheet_status=t.timesheet_status,
            submitted_at=t.submitted_at,
            approved_at=t.approved_at,
        )
        for t in timesheets
    ]


async def get_timesheet_report(
    db: AsyncSession,
    requesting_user: User,
    *,
    project_id: str | None = None,
    client_id: str | None = None,
    employee_id: str | None = None,
    timesheet_status: TimesheetStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[TimesheetReportRow], int]:
    """Role-scoped like the rest of the app: admins see everything, managers see their
    own projects, employees see only their own entries — `list_timesheets` and
    `list_my_timesheets` are NOT interchangeable, so we pick the right one per role.
    """
    if _is_manager_or_admin(requesting_user):
        timesheets, total = await timesheet_service.list_timesheets(
            db,
            requesting_user,
            employee_id=employee_id,
            project_id=project_id,
            client_id=client_id,
            timesheet_status=timesheet_status,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
    else:
        timesheets, total = await timesheet_service.list_my_timesheets(
            db,
            requesting_user.employee_id,
            project_id=project_id,
            client_id=client_id,
            timesheet_status=timesheet_status,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
    return await _to_rows(db, timesheets), total
