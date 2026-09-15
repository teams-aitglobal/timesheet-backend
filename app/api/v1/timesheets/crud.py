from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.enums import TimesheetStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.timesheet import TimesheetCreate, TimesheetOut, TimesheetUpdate
from app.services import timesheet_service

from .common import get_timesheet_or_404

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


@router.post("", response_model=TimesheetOut, status_code=status.HTTP_201_CREATED)
async def create_timesheet(
    payload: TimesheetCreate,
    current_user: User = Depends(require_permission("TIMESHEET_CREATE")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await timesheet_service.create_timesheet(db, payload, current_user)
    return timesheet_service.to_timesheet_out(timesheet)


@router.get("/my", response_model=PaginatedResponse[TimesheetOut])
async def list_my_timesheets(
    project_id: str | None = Query(default=None),
    timesheet_status: TimesheetStatus | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("TIMESHEET_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TimesheetOut]:
    timesheets, total = await timesheet_service.list_my_timesheets(
        db,
        current_user.employee_id,
        project_id=project_id,
        timesheet_status=timesheet_status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(
        items=[timesheet_service.to_timesheet_out(t) for t in timesheets], total=total, skip=skip, limit=limit
    )


@router.get("", response_model=PaginatedResponse[TimesheetOut])
async def list_timesheets(
    employee_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    timesheet_status: TimesheetStatus | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("TIMESHEET_READ")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TimesheetOut]:
    timesheets, total = await timesheet_service.list_timesheets(
        db,
        current_user,
        employee_id=employee_id,
        project_id=project_id,
        task_id=task_id,
        timesheet_status=timesheet_status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(
        items=[timesheet_service.to_timesheet_out(t) for t in timesheets], total=total, skip=skip, limit=limit
    )


@router.get("/{timesheet_id}", response_model=TimesheetOut)
async def get_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_READ")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await get_timesheet_or_404(db, timesheet_id)
    return timesheet_service.to_timesheet_out(timesheet)


@router.patch("/{timesheet_id}", response_model=TimesheetOut)
async def update_timesheet(
    timesheet_id: str,
    payload: TimesheetUpdate,
    current_user: User = Depends(require_permission("TIMESHEET_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.update_timesheet(db, timesheet, payload, current_user)
    return timesheet_service.to_timesheet_out(timesheet)


@router.delete("/{timesheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> None:
    timesheet = await get_timesheet_or_404(db, timesheet_id)
    await timesheet_service.delete_timesheet(db, timesheet, current_user)
