from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.user import User
from app.schemas.project_assignment import (
    MyProjectAssignmentOut,
    ProjectAssignmentCreate,
    ProjectAssignmentOut,
    ProjectAssignmentUpdate,
)
from app.services import project_service, user_service
from app.services.audit_service import AuditAction, create_audit_log

_TRACKED_FIELDS = ("allocated_hours", "start_date", "end_date", "is_active", "remarks")


def _validate_within_project_dates(project: Project, start_date, end_date) -> None:
    if start_date < project.project_start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date cannot be before the project's start date.",
        )
    if project.project_end_date is not None and (end_date or start_date) > project.project_end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assignment dates cannot extend beyond the project's end date.",
        )


def to_project_assignment_out(assignment: ProjectAssignment) -> ProjectAssignmentOut:
    return ProjectAssignmentOut.model_validate(assignment)


def _snapshot(assignment: ProjectAssignment) -> dict:
    snapshot = {field: getattr(assignment, field) for field in _TRACKED_FIELDS}
    for date_field in ("start_date", "end_date"):
        if snapshot[date_field] is not None:
            snapshot[date_field] = snapshot[date_field].isoformat()
    return snapshot


async def get_project_assignment_by_id(db: AsyncSession, project_assignment_id: str) -> ProjectAssignment | None:
    result = await db.execute(
        select(ProjectAssignment).where(ProjectAssignment.project_assignment_id == project_assignment_id)
    )
    return result.scalar_one_or_none()


async def list_project_assignments(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    employee_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ProjectAssignment], int]:
    query = select(ProjectAssignment)
    count_query = select(func.count()).select_from(ProjectAssignment)
    if project_id is not None:
        query = query.where(ProjectAssignment.project_id == project_id)
        count_query = count_query.where(ProjectAssignment.project_id == project_id)
    if employee_id is not None:
        query = query.where(ProjectAssignment.employee_id == employee_id)
        count_query = count_query.where(ProjectAssignment.employee_id == employee_id)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(ProjectAssignment.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def list_my_project_assignments(
    db: AsyncSession, employee_id: str
) -> list[MyProjectAssignmentOut]:
    result = await db.execute(
        select(ProjectAssignment, Project)
        .join(Project, Project.project_id == ProjectAssignment.project_id)
        .where(ProjectAssignment.employee_id == employee_id)
        .order_by(ProjectAssignment.is_active.desc(), ProjectAssignment.start_date.desc())
    )
    return [
        MyProjectAssignmentOut(
            project_assignment_id=assignment.project_assignment_id,
            project_id=project.project_id,
            project_name=project.project_name,
            project_status=project.status,
            project_start_date=project.project_start_date,
            project_end_date=project.project_end_date,
            allocated_hours=assignment.allocated_hours,
            start_date=assignment.start_date,
            end_date=assignment.end_date,
            is_active=assignment.is_active,
            remarks=assignment.remarks,
        )
        for assignment, project in result.all()
    ]


async def _next_project_assignment_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(ProjectAssignment))).scalar_one()
    return f"PA{total + 1:04d}"


async def create_project_assignment(
    db: AsyncSession,
    data: ProjectAssignmentCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProjectAssignment:
    project = await project_service.get_project_by_id(db, data.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if await user_service.get_user_by_id(db, data.employee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    _validate_within_project_dates(project, data.start_date, data.end_date)

    assignment = ProjectAssignment(
        project_assignment_id=await _next_project_assignment_id(db),
        project_id=data.project_id,
        employee_id=data.employee_id,
        allocated_hours=data.allocated_hours,
        start_date=data.start_date,
        end_date=data.end_date,
        remarks=data.remarks,
        created_by=actor.employee_id,
    )
    db.add(assignment)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="project_assignment",
        entity_id=assignment.project_assignment_id,
        new_value=_snapshot(assignment)
        | {"project_id": assignment.project_id, "employee_id": assignment.employee_id},
    )

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def update_project_assignment(
    db: AsyncSession,
    assignment: ProjectAssignment,
    data: ProjectAssignmentUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProjectAssignment:
    changes = data.model_dump(exclude_unset=True)

    new_start = changes.get("start_date", assignment.start_date)
    new_end = changes.get("end_date", assignment.end_date)
    if new_end is not None and new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date cannot be before start_date.",
        )
    if "start_date" in changes or "end_date" in changes:
        project = await project_service.get_project_by_id(db, assignment.project_id)
        if project is not None:
            _validate_within_project_dates(project, new_start, new_end)

    old_values = _snapshot(assignment)

    for field, value in changes.items():
        setattr(assignment, field, value)

    if changes:
        assignment.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="project_assignment",
            entity_id=assignment.project_assignment_id,
            old_value=old_values,
            new_value=_snapshot(assignment),
        )

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def deactivate_project_assignment(
    db: AsyncSession,
    assignment: ProjectAssignment,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProjectAssignment:
    if assignment.is_active:
        assignment.is_active = False
        assignment.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="project_assignment",
            entity_id=assignment.project_assignment_id,
            old_value={"is_active": True},
            new_value={"is_active": False},
        )
        await db.commit()
        await db.refresh(assignment)
    return assignment
