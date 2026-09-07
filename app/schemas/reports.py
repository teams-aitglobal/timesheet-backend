from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import TimesheetStatus, WorkType


class TimesheetReportRow(BaseModel):
    timesheet_id: str
    employee_id: str
    employee_name: str
    work_date: date
    project_id: str
    project_name: str
    work_type: WorkType
    task_id: str | None
    task_name: str | None
    hours: float
    work_description: str
    timesheet_status: TimesheetStatus
    submitted_at: datetime | None
    approved_at: datetime | None


class ProjectHoursReportRow(BaseModel):
    project_id: str
    project_name: str
    client_name: str
    budget_hours: float | None
    hours_logged: float
    remaining_hours: float | None
