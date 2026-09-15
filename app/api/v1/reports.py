from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import require_role
from app.models.enums import TimesheetStatus
from app.models.role import PROJECT_MANAGER, SUPER_ADMIN
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.reports import ProjectHoursReportRow, TimesheetReportRow
from app.services.reports import column_policy, csv_utils, project_hours_report_service, timesheet_report_service

router = APIRouter(prefix="/reports", tags=["reports"])

_CSV_EXPORT_LIMIT = 5000


@router.get("/timesheets", response_model=None)
async def get_timesheet_report(
    project_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    timesheet_status: TimesheetStatus | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    format: Literal["json", "csv"] = Query(default="json"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TimesheetReportRow] | StreamingResponse:
    is_csv = format == "csv"
    rows, total = await timesheet_report_service.get_timesheet_report(
        db,
        current_user,
        project_id=project_id,
        client_id=client_id,
        employee_id=employee_id,
        timesheet_status=timesheet_status,
        date_from=date_from,
        date_to=date_to,
        skip=0 if is_csv else skip,
        limit=_CSV_EXPORT_LIMIT if is_csv else limit,
    )
    if is_csv:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_rows = [column_policy.project_timesheet_row(row, current_user) for row in rows]
        return csv_utils.rows_to_csv_response(csv_rows, filename=f"timesheet_report_{timestamp}.csv")
    return PaginatedResponse(items=rows, total=total, skip=skip, limit=limit)


@router.get("/project-hours", response_model=None)
async def get_project_hours_report(
    client_id: str | None = Query(default=None),
    format: Literal["json", "csv"] = Query(default="json"),
    current_user: User = Depends(require_role(SUPER_ADMIN, PROJECT_MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectHoursReportRow] | StreamingResponse:
    rows = await project_hours_report_service.get_project_hours_report(db, current_user, client_id=client_id)
    if format == "csv":
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_rows = [row.model_dump() for row in rows]
        return csv_utils.rows_to_csv_response(csv_rows, filename=f"project_hours_report_{timestamp}.csv")
    return rows
