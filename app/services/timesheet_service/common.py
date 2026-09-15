from app.models.enums import TimesheetStatus
from app.models.role import SUPER_ADMIN
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.timesheet import TimesheetOut

_EDITABLE_STATUSES = (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED)


def to_timesheet_out(timesheet: Timesheet) -> TimesheetOut:
    return TimesheetOut.model_validate(timesheet)


def _is_admin(user: User) -> bool:
    return any(ur.role.name == SUPER_ADMIN for ur in user.user_roles)
