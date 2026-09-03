import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import EMPLOYEE, SUPER_ADMIN, Role
from app.services import role_service

from .conftest import auth_header, login


async def _role_id(db_session: AsyncSession, name: str) -> str:
    result = await db_session.execute(select(Role).where(Role.name == name))
    return str(result.scalar_one().id)


async def test_employee_denied_user_create(client: AsyncClient, employee, db_session: AsyncSession):
    user, password = employee
    tokens = await login(client, user.email, password)
    role_id = await _role_id(db_session, EMPLOYEE)

    response = await client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "first_name": "X", "last_name": "Y", "role_ids": [role_id]},
        headers=auth_header(tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_program_manager_denied_user_create_by_default(
    client: AsyncClient, program_manager, db_session: AsyncSession
):
    user, password = program_manager
    tokens = await login(client, user.email, password)
    role_id = await _role_id(db_session, EMPLOYEE)

    response = await client.post(
        "/api/v1/users",
        json={"email": "x2@example.com", "first_name": "X", "last_name": "Y", "role_ids": [role_id]},
        headers=auth_header(tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_super_admin_allowed_user_create(client: AsyncClient, super_admin, db_session: AsyncSession):
    user, password = super_admin
    tokens = await login(client, user.email, password)
    role_id = await _role_id(db_session, EMPLOYEE)

    response = await client.post(
        "/api/v1/users",
        json={"email": "x3@example.com", "first_name": "X", "last_name": "Y", "role_ids": [role_id]},
        headers=auth_header(tokens["access_token"]),
    )
    assert response.status_code == 201


async def test_employee_denied_role_assign(client: AsyncClient, employee, db_session: AsyncSession):
    user, password = employee
    tokens = await login(client, user.email, password)
    role_id = await _role_id(db_session, EMPLOYEE)

    response = await client.post(
        f"/api/v1/users/{user.employee_id}/roles",
        json={"role_ids": [role_id]},
        headers=auth_header(tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_super_admin_allowed_role_assign(
    client: AsyncClient, super_admin, program_manager, db_session: AsyncSession
):
    admin, admin_password = super_admin
    target, _ = program_manager
    tokens = await login(client, admin.email, admin_password)
    role_id = await _role_id(db_session, EMPLOYEE)

    response = await client.post(
        f"/api/v1/users/{target.employee_id}/roles",
        json={"role_ids": [role_id]},
        headers=auth_header(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert set(response.json()["roles"]) == {"PROGRAM_MANAGER", "EMPLOYEE"}


async def test_only_super_admin_can_assign_super_admin_role(program_manager, super_admin):
    pm_user, _ = program_manager
    admin_user, _ = super_admin
    super_admin_role = Role(name=SUPER_ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        role_service.assert_can_assign_roles(pm_user, {"PROGRAM_MANAGER"}, [super_admin_role])
    assert exc_info.value.status_code == 403

    # Should not raise for an actor who holds SUPER_ADMIN.
    role_service.assert_can_assign_roles(admin_user, {SUPER_ADMIN}, [super_admin_role])
