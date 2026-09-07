from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.enums import ProjectStatus, TaskStatus


class EmployeeProjectSummary(BaseModel):
    project_id: str
    project_name: str
    client_id: str
    client_name: str
    project_status: ProjectStatus


class EmployeeTaskSummary(BaseModel):
    task_id: str
    task_name: str
    project_name: str
    status: TaskStatus
    due_date: date | None


class EmployeeDashboardOut(BaseModel):
    role: Literal["EMPLOYEE"] = "EMPLOYEE"
    active_projects: int
    remaining_tasks: int
    draft_timesheets: int
    projects: list[EmployeeProjectSummary]
    tasks: list[EmployeeTaskSummary]


class ManagerProjectSummary(BaseModel):
    project_id: str
    project_name: str
    client_id: str
    client_name: str
    status: ProjectStatus
    project_start_date: date
    project_end_date: date | None
    team_size: int
    budget_hours: float | None
    hours_logged: float


class ManagerDashboardOut(BaseModel):
    role: Literal["PROGRAM_MANAGER"] = "PROGRAM_MANAGER"
    my_projects: int
    clients: int
    team_members: int
    pending_approvals: int
    hours_awaiting_approval: float
    projects: list[ManagerProjectSummary]


class AdminDashboardOut(BaseModel):
    role: Literal["SUPER_ADMIN"] = "SUPER_ADMIN"
    total_clients: int
    active_projects: int
    total_employees: int
    pending_approvals: int
    hours_awaiting_approval: float
