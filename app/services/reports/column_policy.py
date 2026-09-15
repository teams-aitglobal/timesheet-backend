from app.models.role import PROJECT_MANAGER, SUPER_ADMIN
from app.models.user import User
from app.schemas.reports import TimesheetReportRow

# Employees already only ever see their own rows (row-scoping happens in
# timesheet_report_service), so this is about export readability, not access
# control — dropping internal IDs and audit timestamps they have no use for.
_TIMESHEET_EMPLOYEE_COLUMNS = (
    "employee_name",
    "work_date",
    "project_name",
    "client_name",
    "work_type",
    "task_name",
    "hours",
    "work_description",
    "timesheet_status",
)


def project_timesheet_row(row: TimesheetReportRow, user: User) -> dict:
    """Trims CSV export columns for employees; Super Admin/Project Manager get every field."""
    data = row.model_dump()
    role_names = {ur.role.name for ur in user.user_roles}
    if role_names & {SUPER_ADMIN, PROJECT_MANAGER}:
        return data
    return {k: v for k, v in data.items() if k in _TIMESHEET_EMPLOYEE_COLUMNS}
