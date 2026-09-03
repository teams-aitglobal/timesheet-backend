from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TOKEN_TYPE_ACCESS
from app.models.role import EMPLOYEE, Role
from app.models.user import User

from .conftest import auth_header, login


async def test_successful_login(client: AsyncClient, super_admin):
    user, password = super_admin
    body = await login(client, user.email, password)
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["must_change_password"] is False


async def test_invalid_password(client: AsyncClient, super_admin):
    user, _password = super_admin
    response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
    assert response.status_code == 401


async def test_inactive_user_cannot_login(client: AsyncClient, employee, db_session: AsyncSession):
    user, password = employee
    user_in_db = await db_session.get(User, user.employee_id)
    user_in_db.status = "Inactive"
    await db_session.commit()

    response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert response.status_code == 401


async def test_invalid_jwt_rejected(client: AsyncClient):
    response = await client.get("/api/v1/auth/me", headers=auth_header("not-a-real-token"))
    assert response.status_code == 401


async def test_expired_jwt_rejected(client: AsyncClient, super_admin):
    user, _password = super_admin
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": user.employee_id,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.get("/api/v1/auth/me", headers=auth_header(expired_token))
    assert response.status_code == 401


async def test_refresh_token_flow(client: AsyncClient, super_admin):
    user, password = super_admin
    tokens = await login(client, user.email, password)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


async def test_revoked_refresh_token_rejected(client: AsyncClient, super_admin):
    user, password = super_admin
    tokens = await login(client, user.email, password)

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200

    # Reusing the now-rotated-out original refresh token must fail.
    second = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert second.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient, super_admin):
    user, password = super_admin
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 401


async def test_change_password(client: AsyncClient, super_admin):
    user, password = super_admin
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "BrandNewPassword123!"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False

    old_login = await client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "BrandNewPassword123!"}
    )
    assert new_login.status_code == 200


async def test_first_login_forces_password_change(client: AsyncClient, db_session: AsyncSession):
    result = await db_session.execute(select(Role).where(Role.name == EMPLOYEE))
    employee_role = result.scalar_one()

    from app.core.security import hash_password
    from app.models.user_role import UserRole
    from app.services.user_service import next_employee_id

    temp_password = "TemporaryPass123!"
    new_user = User(
        employee_id=await next_employee_id(db_session),
        email="newhire@example.com",
        password_hash=hash_password(temp_password),
        first_name="New",
        last_name="Hire",
        must_change_password=True,
    )
    db_session.add(new_user)
    await db_session.flush()
    db_session.add(UserRole(user_id=new_user.employee_id, role_id=employee_role.id))
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": new_user.email, "password": temp_password}
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True

    headers = auth_header(login_response.json()["access_token"])
    change_response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temp_password, "new_password": "PermanentPass123!"},
        headers=headers,
    )
    assert change_response.status_code == 200
    assert change_response.json()["must_change_password"] is False


async def test_me_returns_roles_and_permissions_without_secrets(client: AsyncClient, super_admin):
    user, password = super_admin
    tokens = await login(client, user.email, password)
    response = await client.get("/api/v1/auth/me", headers=auth_header(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert "SUPER_ADMIN" in body["roles"]
    assert "USER_CREATE" in body["permissions"]
    assert "password_hash" not in body
    assert "password" not in body
