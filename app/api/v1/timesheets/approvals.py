from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.authorization import require_permission
from app.models.timesheet import Timesheet
from app.models.user import User
from app.schemas.timesheet import (
    PendingApprovalSummary,
    TimesheetBulkAction,
    TimesheetBulkActionResult,
    TimesheetOut,
    TimesheetReject,
)
from app.services import timesheet_service

from .common import get_timesheet_or_404

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


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


@router.post("/{timesheet_id}/submit", response_model=TimesheetOut)
async def submit_timesheet(
    timesheet_id: str,
    current_user: User = Depends(require_permission("TIMESHEET_SUBMIT")),
    db: AsyncSession = Depends(get_db),
) -> TimesheetOut:
    timesheet = await get_timesheet_or_404(db, timesheet_id)
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
    timesheet = await get_timesheet_or_404(db, timesheet_id)
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
    timesheet = await get_timesheet_or_404(db, timesheet_id)
    timesheet = await timesheet_service.reject_timesheet(db, timesheet, current_user, payload.rejection_reason)
    return timesheet_service.to_timesheet_out(timesheet)
