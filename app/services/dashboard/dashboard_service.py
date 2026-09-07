from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import PROGRAM_MANAGER, SUPER_ADMIN
from app.models.user import User
from app.schemas.dashboard import (
    AdminDashboardOut,
    EmployeeDashboardOut,
    ManagerDashboardOut,
)
from app.services.dashboard import widgets


def _role_names(user: User) -> set[str]:
    return {ur.role.name for ur in user.user_roles}


async def _build_admin_dashboard(db: AsyncSession, user: User) -> AdminDashboardOut:
    total_clients, active_projects, total_employees = await widgets.admin_org_overview(db)
    pending_approvals, hours_awaiting_approval = await widgets.pending_approvals_summary(db, user)
    return AdminDashboardOut(
        total_clients=total_clients,
        active_projects=active_projects,
        total_employees=total_employees,
        pending_approvals=pending_approvals,
        hours_awaiting_approval=hours_awaiting_approval,
    )


async def _build_manager_dashboard(db: AsyncSession, user: User) -> ManagerDashboardOut:
    projects = await widgets.manager_project_overview(db, user.employee_id)
    project_ids = [p.project_id for p in projects]
    team_members = await widgets.distinct_team_member_count(db, project_ids)
    pending_approvals, hours_awaiting_approval = await widgets.pending_approvals_summary(db, user)
    return ManagerDashboardOut(
        my_projects=len(projects),
        clients=len({p.client_id for p in projects}),
        team_members=team_members,
        pending_approvals=pending_approvals,
        hours_awaiting_approval=hours_awaiting_approval,
        projects=projects,
    )


async def _build_employee_dashboard(db: AsyncSession, user: User) -> EmployeeDashboardOut:
    projects = await widgets.employee_projects(db, user.employee_id)
    remaining_tasks, tasks = await widgets.employee_tasks(db, user.employee_id)
    draft_timesheets = await widgets.employee_draft_timesheet_count(db, user.employee_id)
    return EmployeeDashboardOut(
        active_projects=len(projects),
        remaining_tasks=remaining_tasks,
        draft_timesheets=draft_timesheets,
        projects=projects,
        tasks=tasks,
    )


async def get_dashboard(
    db: AsyncSession, user: User
) -> AdminDashboardOut | ManagerDashboardOut | EmployeeDashboardOut:
    role_names = _role_names(user)
    if SUPER_ADMIN in role_names:
        return await _build_admin_dashboard(db, user)
    if PROGRAM_MANAGER in role_names:
        return await _build_manager_dashboard(db, user)
    return await _build_employee_dashboard(db, user)
