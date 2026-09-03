from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import EMPLOYEE, Role

from .conftest import auth_header, login


async def _employee_role_id(db_session: AsyncSession) -> str:
    from sqlalchemy import select

    result = await db_session.execute(select(Role).where(Role.name == EMPLOYEE))
    return str(result.scalar_one().id)


async def test_super_admin_creates_user(client: AsyncClient, super_admin, db_session: AsyncSession):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    role_id = await _employee_role_id(db_session)

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "hired@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "role_ids": [role_id],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "hired@example.com"
    assert body["roles"] == [EMPLOYEE]
    assert body["must_change_password"] is True
    assert body["temporary_password"]


async def test_duplicate_email_rejected(client: AsyncClient, super_admin, employee, db_session: AsyncSession):
    admin, password = super_admin
    existing_user, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    role_id = await _employee_role_id(db_session)

    response = await client.post(
        "/api/v1/users",
        json={
            "email": existing_user.email,
            "first_name": "Dup",
            "last_name": "Licate",
            "role_ids": [role_id],
        },
        headers=headers,
    )
    assert response.status_code == 409


async def test_unauthenticated_user_creation_rejected(client: AsyncClient, db_session: AsyncSession):
    role_id = await _employee_role_id(db_session)
    response = await client.post(
        "/api/v1/users",
        json={"email": "nobody@example.com", "first_name": "No", "last_name": "Body", "role_ids": [role_id]},
    )
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_user(client: AsyncClient, employee, db_session: AsyncSession):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])
    role_id = await _employee_role_id(db_session)

    response = await client.post(
        "/api/v1/users",
        json={"email": "blocked@example.com", "first_name": "Blocked", "last_name": "User", "role_ids": [role_id]},
        headers=headers,
    )
    assert response.status_code == 403


async def test_super_admin_deactivates_user(client: AsyncClient, super_admin, employee):
    admin, password = super_admin
    target, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.delete(f"/api/v1/users/{target.employee_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Inactive"


async def test_deactivated_user_cannot_login(client: AsyncClient, super_admin, employee):
    admin, admin_password = super_admin
    target, target_password = employee
    tokens = await login(client, admin.email, admin_password)
    headers = auth_header(tokens["access_token"])

    deactivate_response = await client.delete(f"/api/v1/users/{target.employee_id}", headers=headers)
    assert deactivate_response.status_code == 200

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": target_password}
    )
    assert login_response.status_code == 401
