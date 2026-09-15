from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TimesheetStatus
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.models.user import User
from app.services import project_service
from app.services.audit_service import AuditAction, create_audit_log

from .common import _EDITABLE_STATUSES, _is_admin


async def submit_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User) -> Timesheet:
    if timesheet.employee_id != actor.employee_id and not _is_admin(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this timesheet entry.")
    if timesheet.timesheet_status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot submit a timesheet in {timesheet.timesheet_status.value} status.",
        )

    old_status = timesheet.timesheet_status
    timesheet.timesheet_status = TimesheetStatus.SUBMITTED
    timesheet.submitted_at = datetime.now(timezone.utc)
    timesheet.rejection_reason = None

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": old_status.value},
        new_value={"timesheet_status": TimesheetStatus.SUBMITTED.value, "submitted_at": timesheet.submitted_at.isoformat()},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


def _assert_can_review(timesheet: Timesheet, project: Project, actor: User) -> None:
    if not _is_admin(actor) and project.project_manager_id != actor.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not manage the project for this timesheet entry."
        )
    if timesheet.timesheet_status != TimesheetStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot review a timesheet in {timesheet.timesheet_status.value} status.",
        )


async def approve_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User) -> Timesheet:
    project = await project_service.get_project_by_id(db, timesheet.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    _assert_can_review(timesheet, project, actor)

    timesheet.timesheet_status = TimesheetStatus.APPROVED
    timesheet.approved_at = datetime.now(timezone.utc)
    timesheet.approved_by = actor.employee_id

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": TimesheetStatus.SUBMITTED.value},
        new_value={"timesheet_status": TimesheetStatus.APPROVED.value, "approved_by": actor.employee_id},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


async def reject_timesheet(db: AsyncSession, timesheet: Timesheet, actor: User, rejection_reason: str) -> Timesheet:
    project = await project_service.get_project_by_id(db, timesheet.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    _assert_can_review(timesheet, project, actor)

    timesheet.timesheet_status = TimesheetStatus.REJECTED
    timesheet.rejection_reason = rejection_reason

    await create_audit_log(
        db,
        action=AuditAction.UPDATED,
        changed_by=actor.employee_id,
        entity_type="timesheet",
        entity_id=timesheet.timesheet_id,
        old_value={"timesheet_status": TimesheetStatus.SUBMITTED.value},
        new_value={"timesheet_status": TimesheetStatus.REJECTED.value, "rejection_reason": rejection_reason},
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet
