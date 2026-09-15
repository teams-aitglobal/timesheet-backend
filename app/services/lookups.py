"""Small id -> display-name lookup helpers shared by the dashboard and reports services.

Existing list_* service functions return full rows scoped/paginated for their own
screens; dashboards and reports just need a cheap id -> name map for a known set of
ids, so that's kept separate rather than bolted onto those functions.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


async def client_names_by_id(db: AsyncSession, client_ids: set[str]) -> dict[str, str]:
    if not client_ids:
        return {}
    result = await db.execute(select(Client.client_id, Client.client_name).where(Client.client_id.in_(client_ids)))
    return dict(result.all())


async def project_names_by_id(db: AsyncSession, project_ids: set[str]) -> dict[str, str]:
    if not project_ids:
        return {}
    result = await db.execute(
        select(Project.project_id, Project.project_name).where(Project.project_id.in_(project_ids))
    )
    return dict(result.all())


async def project_client_ids_by_id(db: AsyncSession, project_ids: set[str]) -> dict[str, str]:
    if not project_ids:
        return {}
    result = await db.execute(
        select(Project.project_id, Project.client_id).where(Project.project_id.in_(project_ids))
    )
    return dict(result.all())


async def task_names_by_id(db: AsyncSession, task_ids: set[str]) -> dict[str, str]:
    if not task_ids:
        return {}
    result = await db.execute(select(Task.task_id, Task.task_name).where(Task.task_id.in_(task_ids)))
    return dict(result.all())


async def employee_names_by_id(db: AsyncSession, employee_ids: set[str]) -> dict[str, str]:
    if not employee_ids:
        return {}
    result = await db.execute(
        select(User.employee_id, User.first_name, User.last_name).where(User.employee_id.in_(employee_ids))
    )
    return {employee_id: f"{first} {last}" for employee_id, first, last in result.all()}
