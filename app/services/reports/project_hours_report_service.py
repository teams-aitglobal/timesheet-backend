from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import SUPER_ADMIN
from app.models.user import User
from app.schemas.reports import ProjectHoursReportRow
from app.services import lookups, project_service, timesheet_service


def _is_admin(user: User) -> bool:
    return any(ur.role.name == SUPER_ADMIN for ur in user.user_roles)


async def get_project_hours_report(
    db: AsyncSession, requesting_user: User, *, client_id: str | None = None
) -> list[ProjectHoursReportRow]:
    project_manager_id = None if _is_admin(requesting_user) else requesting_user.employee_id
    projects, _ = await project_service.list_projects(
        db, client_id=client_id, project_manager_id=project_manager_id, limit=500
    )
    if not projects:
        return []

    client_names = await lookups.client_names_by_id(db, {p.client_id for p in projects})
    hours_logged = await timesheet_service.sum_hours_by_project(db, [p.project_id for p in projects])

    rows = []
    for p in projects:
        logged = hours_logged.get(p.project_id, 0.0)
        rows.append(
            ProjectHoursReportRow(
                project_id=p.project_id,
                project_name=p.project_name,
                client_name=client_names.get(p.client_id, "—"),
                budget_hours=p.budget_hours,
                hours_logged=logged,
                remaining_hours=None if p.budget_hours is None else p.budget_hours - logged,
            )
        )
    return rows
