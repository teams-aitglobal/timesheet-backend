from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus, TaskStatus, TimesheetStatus
from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.user import User
from app.schemas.dashboard import (
    EmployeeProjectSummary,
    EmployeeTaskSummary,
    ManagerProjectSummary,
)
from app.services import (
    client_service,
    lookups,
    project_assignment_service,
    project_service,
    task_service,
    timesheet_service,
    user_service,
)

_REMAINING_TASK_STATUSES = (TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.ON_HOLD)
_MAX_DASHBOARD_TASKS = 8


async def _team_size_by_project(db: AsyncSession, project_ids: list[str]) -> dict[str, int]:
    if not project_ids:
        return {}
    result = await db.execute(
        select(ProjectAssignment.project_id, func.count(distinct(ProjectAssignment.employee_id)))
        .where(ProjectAssignment.project_id.in_(project_ids), ProjectAssignment.is_active.is_(True))
        .group_by(ProjectAssignment.project_id)
    )
    return dict(result.all())


async def distinct_team_member_count(db: AsyncSession, project_ids: list[str]) -> int:
    if not project_ids:
        return 0
    result = await db.execute(
        select(func.count(distinct(ProjectAssignment.employee_id))).where(
            ProjectAssignment.project_id.in_(project_ids), ProjectAssignment.is_active.is_(True)
        )
    )
    return result.scalar_one()


async def employee_projects(db: AsyncSession, employee_id: str) -> list[EmployeeProjectSummary]:
    assignments = await project_assignment_service.list_my_project_assignments(db, employee_id)
    active = [a for a in assignments if a.is_active]
    if not active:
        return []
    project_ids = {a.project_id for a in active}
    result = await db.execute(select(Project.project_id, Project.client_id).where(Project.project_id.in_(project_ids)))
    client_id_by_project = dict(result.all())
    client_names = await lookups.client_names_by_id(db, set(client_id_by_project.values()))
    return [
        EmployeeProjectSummary(
            project_id=a.project_id,
            project_name=a.project_name,
            client_id=client_id_by_project.get(a.project_id, ""),
            client_name=client_names.get(client_id_by_project.get(a.project_id, ""), "—"),
            project_status=a.project_status,
        )
        for a in active
    ]


async def employee_tasks(db: AsyncSession, employee_id: str) -> tuple[int, list[EmployeeTaskSummary]]:
    my_tasks = await task_service.list_my_tasks(db, employee_id)
    remaining = [t for t in my_tasks if t.status in _REMAINING_TASK_STATUSES]
    project_names = await lookups.project_names_by_id(db, {t.project_id for t in remaining})
    remaining.sort(key=lambda t: (t.due_date is None, t.due_date))
    tasks = [
        EmployeeTaskSummary(
            task_id=t.task_id,
            task_name=t.task_name,
            project_name=project_names.get(t.project_id, "—"),
            status=t.status,
            due_date=t.due_date,
        )
        for t in remaining[:_MAX_DASHBOARD_TASKS]
    ]
    return len(remaining), tasks


async def employee_draft_timesheet_count(db: AsyncSession, employee_id: str) -> int:
    _, total = await timesheet_service.list_my_timesheets(
        db, employee_id, timesheet_status=TimesheetStatus.DRAFT, skip=0, limit=1
    )
    return total


async def manager_project_overview(db: AsyncSession, project_manager_id: str) -> list[ManagerProjectSummary]:
    projects, _ = await project_service.list_projects(db, project_manager_id=project_manager_id, limit=200)
    if not projects:
        return []
    project_ids = [p.project_id for p in projects]
    client_names = await lookups.client_names_by_id(db, {p.client_id for p in projects})
    team_sizes = await _team_size_by_project(db, project_ids)
    hours_logged = await timesheet_service.sum_hours_by_project(db, project_ids)
    return [
        ManagerProjectSummary(
            project_id=p.project_id,
            project_name=p.project_name,
            client_id=p.client_id,
            client_name=client_names.get(p.client_id, "—"),
            status=p.status,
            project_start_date=p.project_start_date,
            project_end_date=p.project_end_date,
            team_size=team_sizes.get(p.project_id, 0),
            budget_hours=p.budget_hours,
            hours_logged=hours_logged.get(p.project_id, 0.0),
        )
        for p in projects
    ]


async def pending_approvals_summary(db: AsyncSession, requesting_user: User) -> tuple[int, float]:
    _, total, total_hours = await timesheet_service.list_pending_approval(db, requesting_user, limit=1)
    return total, total_hours


async def admin_org_overview(db: AsyncSession) -> tuple[int, int, int]:
    _, total_clients = await client_service.list_clients(db, limit=1)
    _, active_project_count = await project_service.list_projects(db, status_filter=ProjectStatus.ACTIVE, limit=1)
    _, total_employees = await user_service.list_users(db, limit=1)
    return total_clients, active_project_count, total_employees
