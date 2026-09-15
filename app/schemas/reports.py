from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel, field_serializer

from app.models.enums import TimesheetStatus, WorkType

IST = timezone(timedelta(hours=5, minutes=30))


class TimesheetReportRow(BaseModel):
    timesheet_id: str
    employee_id: str
    employee_name: str
    work_date: date
    project_id: str
    project_name: str
    client_id: str
    client_name: str
    work_type: WorkType
    task_id: str | None
    task_name: str | None
    hours: float
    work_description: str
    timesheet_status: TimesheetStatus
    submitted_at: datetime | None
    approved_at: datetime | None

    @field_serializer("submitted_at", "approved_at")
    def _format_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


class ProjectHoursReportRow(BaseModel):
    project_id: str
    project_name: str
    client_name: str
    budget_hours: float | None
    hours_logged: float
    remaining_hours: float | None
