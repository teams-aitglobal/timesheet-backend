from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import client_service, client_spoc_service, user_service
from app.services.audit_service import AuditAction, create_audit_log

_TRACKED_FIELDS = (
    "project_name",
    "project_manager_id",
    "client_spoc_id",
    "project_start_date",
    "project_end_date",
    "project_description",
    "budget_hours",
    "status",
)


def to_project_out(project: Project) -> ProjectOut:
    return ProjectOut.model_validate(project)


def _snapshot(project: Project) -> dict:
    snapshot = {field: getattr(project, field) for field in _TRACKED_FIELDS}
    for date_field in ("project_start_date", "project_end_date"):
        if snapshot[date_field] is not None:
            snapshot[date_field] = snapshot[date_field].isoformat()
    return snapshot


async def get_project_by_id(db: AsyncSession, project_id: str) -> Project | None:
    result = await db.execute(select(Project).where(Project.project_id == project_id))
    return result.scalar_one_or_none()


async def list_projects(
    db: AsyncSession,
    *,
    client_id: str | None = None,
    project_manager_id: str | None = None,
    status_filter: ProjectStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Project], int]:
    query = select(Project)
    count_query = select(func.count()).select_from(Project)
    if client_id is not None:
        query = query.where(Project.client_id == client_id)
        count_query = count_query.where(Project.client_id == client_id)
    if project_manager_id is not None:
        query = query.where(Project.project_manager_id == project_manager_id)
        count_query = count_query.where(Project.project_manager_id == project_manager_id)
    if status_filter is not None:
        query = query.where(Project.status == status_filter)
        count_query = count_query.where(Project.status == status_filter)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Project.created_at).offset(skip).limit(limit))
    return list(result.scalars().all()), total


async def _next_project_id(db: AsyncSession) -> str:
    total = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    return f"PRJ{total + 1:04d}"


async def _validate_client_spoc(db: AsyncSession, client_id: str, client_spoc_id: str | None) -> None:
    if client_spoc_id is None:
        return
    spoc = await client_spoc_service.get_client_spoc_by_id(db, client_spoc_id)
    if spoc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client SPOC not found.")
    if spoc.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client SPOC does not belong to the given client.",
        )


async def create_project(
    db: AsyncSession,
    data: ProjectCreate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Project:
    if await client_service.get_client_by_id(db, data.client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    if await user_service.get_user_by_id(db, data.project_manager_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project manager not found.")
    await _validate_client_spoc(db, data.client_id, data.client_spoc_id)

    project = Project(
        project_id=await _next_project_id(db),
        project_name=data.project_name,
        client_id=data.client_id,
        project_manager_id=data.project_manager_id,
        client_spoc_id=data.client_spoc_id,
        project_start_date=data.project_start_date,
        project_end_date=data.project_end_date,
        project_description=data.project_description,
        budget_hours=data.budget_hours,
        created_by=actor.employee_id,
    )
    db.add(project)
    await db.flush()

    await create_audit_log(
        db,
        action=AuditAction.CREATED,
        changed_by=actor.employee_id,
        entity_type="project",
        entity_id=project.project_id,
        new_value=_snapshot(project) | {"client_id": project.client_id},
    )

    await db.commit()
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession,
    project: Project,
    data: ProjectUpdate,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Project:
    changes = data.model_dump(exclude_unset=True)

    if "project_manager_id" in changes and await user_service.get_user_by_id(db, changes["project_manager_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project manager not found.")
    if "client_spoc_id" in changes:
        await _validate_client_spoc(db, project.client_id, changes["client_spoc_id"])

    new_start = changes.get("project_start_date", project.project_start_date)
    new_end = changes.get("project_end_date", project.project_end_date)
    if new_end is not None and new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_end_date cannot be before project_start_date.",
        )

    old_values = _snapshot(project)

    for field, value in changes.items():
        setattr(project, field, value)

    if changes:
        project.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.UPDATED,
            changed_by=actor.employee_id,
            entity_type="project",
            entity_id=project.project_id,
            old_value=old_values,
            new_value=_snapshot(project),
        )

    await db.commit()
    await db.refresh(project)
    return project


async def deactivate_project(
    db: AsyncSession,
    project: Project,
    actor: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Project:
    if project.status != ProjectStatus.INACTIVE:
        project.status = ProjectStatus.INACTIVE
        project.updated_by = actor.employee_id
        await create_audit_log(
            db,
            action=AuditAction.DEACTIVATED,
            changed_by=actor.employee_id,
            entity_type="project",
            entity_id=project.project_id,
            old_value={"status": ProjectStatus.ACTIVE.value},
            new_value={"status": ProjectStatus.INACTIVE.value},
        )
        await db.commit()
        await db.refresh(project)
    return project
