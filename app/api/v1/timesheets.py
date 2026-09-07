from collections.abc import Awaitable, Callable
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.enums import TimesheetStatus
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.timesheet import (
    PendingApprovalSummary,
    TimesheetBulkAction,
    TimesheetBulkActionResult,
    TimesheetCreate,
    TimesheetOut,
    TimesheetReject,
    TimesheetUpdate,
)
from app.services import timesheet_service

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


async def _get_timesheet_or_404(db: AsyncSession, timesheet_id: str) -> Timesheet:
    timesheet = await timesheet_service.get_timesheet_by_id(db, timesheet_id)
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet entry not found.")
    return timesheet


async def _bulk_apply(
    db: AsyncSession,
    timesheet_ids: list[str],
    action: Callable[[Timesheet], Awaitable[Timesheet]],
) -> TimesheetBulkActionResult:
    updated: list[TimesheetOut] = []
    failed: dict[str, str] = {}
    for timesheet_id in timesheet_ids:
        timesheet = await timesheet_service.get_timesheet_by_id(db, timesheet_id)
        if timesheet is None:
            failed[timesheet_id] = "Timesheet entry not found."
            continue
        try:
            timesheet = await action(timesheet)
        except HTTPException as exc:
            failed[timesheet_id] = str(exc.detail)
            continue
        updated.append(timesheet_service.to_timesheet_out(timesheet))
    return TimesheetBulkActionResult(updated=updated, failed=failed)


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


@router.get("/pending-approval", response_model=PendingApprovalSummary)
async def list_pending_approval(
    project_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_permission("TIMESHEET_APPROVE")),
    db: AsyncSession = Depends(get_db),
) -> PendingApprovalSummary:
    timesheets, total, total_hours = await timesheet_service.list_pending_approval(
        db, current_user, project_id=project_id, skip=skip, limit=limit
    )
    return PendingApprovalSummary(
        items=[timesheet_service.to_timesheet_out(t) for t in timesheets],
        total=total,
        total_hours=total_hours,
        skip=skip,
        limit=limit,
    )


@router.get("/{timesheet_id}", response_model=TimesheetOut)
async def get_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_READ")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    return timesheet_service.to_timesheet_out(timesheet)


@router.patch("/{timesheet_id}", response_model=TimesheetOut)
async def update_timesheet(
    timesheet_id: str,
    payload: TimesheetUpdate,
    current_user: User = Depends(require_permission("TIMESHEET_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.update_timesheet(db, timesheet, payload, current_user)
    return timesheet_service.to_timesheet_out(timesheet)


@router.delete("/{timesheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_UPDATE")),
    db: AsyncSession = Depends(get_db),
) -> None:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    await timesheet_service.delete_timesheet(db, timesheet, current_user)


@router.post("/{timesheet_id}/submit", response_model=TimesheetOut)
async def submit_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_SUBMIT")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.submit_timesheet(db, timesheet, current_user)
    return timesheet_service.to_timesheet_out(timesheet)


@router.post("/submit-bulk", response_model=TimesheetBulkActionResult)
async def submit_timesheets_bulk(
    payload: TimesheetBulkAction,
    current_user: User = Depends(require_permission("TIMESHEET_SUBMIT")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetBulkActionResult:
    return await _bulk_apply(
        db, payload.timesheet_ids, lambda t: timesheet_service.submit_timesheet(db, t, current_user)
    )


@router.post("/{timesheet_id}/approve", response_model=TimesheetOut)
async def approve_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_APPROVE")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.approve_timesheet(db, timesheet, current_user)
    return timesheet_service.to_timesheet_out(timesheet)


@router.post("/approve-bulk", response_model=TimesheetBulkActionResult)
async def approve_timesheets_bulk(
    payload: TimesheetBulkAction,
    current_user: User = Depends(require_permission("TIMESHEET_APPROVE")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetBulkActionResult:
    return await _bulk_apply(
        db, payload.timesheet_ids, lambda t: timesheet_service.approve_timesheet(db, t, current_user)
    )


@router.post("/{timesheet_id}/reject", response_model=TimesheetOut)
async def reject_timesheet(
    timesheet_id: str,
    payload: TimesheetReject,
    current_user: User = Depends(require_permission("TIMESHEET_REJECT")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await _get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.reject_timesheet(db, timesheet, current_user, payload.rejection_reason)
    return timesheet_service.to_timesheet_out(timesheet)
