import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import *
from app.models.role import EMPLOYEE, PROGRAM_MANAGER, SUPER_ADMIN, Role
from app.models.user import User
from app.models.user_role import UserRole
from app.scripts.seed_data import apply_seed_data
from app.services.user_service import next_employee_id

# NullPool: this engine is reused across many independent per-test event loops
# (pytest-asyncio's default function-scoped loop). Pooled asyncpg connections
# are bound to the loop they were opened in, so pooling here would hand a
# connection from a closed loop to a later test. NullPool opens a fresh
# connection per checkout instead, which is safe across loops.
TEST_ENGINE = create_async_engine(settings.DATABASE_URL_TEST, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=TEST_ENGINE, class_=AsyncSession, expire_on_commit=False)

MUTABLE_TABLES = [
    "audit_logs",
    "client_spocs",
    "clients",
    "project_assignments",
    "projects",
    "refresh_tokens",
    "task_assignments",
    "tasks",
    "timesheets",
    "user_roles",
    "users",
]


async def _prepare_database() -> None:
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as db:
        await apply_seed_data(db)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    # Runs in its own throwaway event loop via asyncio.run(), independent of
    # pytest-asyncio's per-test loops - see the NullPool note above.
    asyncio.run(_prepare_database())
    yield


@pytest.fixture(autouse=True)
async def _reset_mutable_tables():
    async with TEST_ENGINE.begin() as conn:
        for table in MUTABLE_TABLES:
            await conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
    yield


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def roles_by_name(db_session: AsyncSession) -> dict[str, Role]:
    result = await db_session.execute(select(Role))
    return {r.name: r for r in result.scalars().all()}


async def _create_user(
    db_session: AsyncSession,
    roles_by_name: dict[str, Role],
    *,
    email: str,
    password: str,
    role_names: list[str],
    must_change_password: bool = False,
) -> User:
    user = User(
        employee_id=await next_employee_id(db_session),
        email=email,
        password_hash=hash_password(password),
        first_name="Test",
        last_name="User",
        is_verified=True,
        must_change_password=must_change_password,
    )
    db_session.add(user)
    await db_session.flush()

    for role_name in role_names:
        db_session.add(UserRole(user_id=user.employee_id, role_id=roles_by_name[role_name].id))

    await db_session.commit()
    await db_session.refresh(user, attribute_names=["user_roles"])
    return user


@pytest.fixture
async def super_admin(db_session: AsyncSession, roles_by_name: dict[str, Role]) -> tuple[User, str]:
    password = "SuperSecret123!"
    user = await _create_user(
        db_session, roles_by_name, email="superadmin@example.com", password=password, role_names=[SUPER_ADMIN]
    )
    return user, password


@pytest.fixture
async def program_manager(db_session: AsyncSession, roles_by_name: dict[str, Role]) -> tuple[User, str]:
    password = "ManagerSecret123!"
    user = await _create_user(
        db_session,
        roles_by_name,
        email="manager@example.com",
        password=password,
        role_names=[PROGRAM_MANAGER],
    )
    return user, password


@pytest.fixture
async def employee(db_session: AsyncSession, roles_by_name: dict[str, Role]) -> tuple[User, str]:
    password = "EmployeeSecret123!"
    user = await _create_user(
        db_session, roles_by_name, email="employee@example.com", password=password, role_names=[EMPLOYEE]
    )
    return user, password


@pytest.fixture
async def other_employee(db_session: AsyncSession, roles_by_name: dict[str, Role]) -> tuple[User, str]:
    password = "OtherEmployeeSecret123!"
    user = await _create_user(
        db_session, roles_by_name, email="other.employee@example.com", password=password, role_names=[EMPLOYEE]
    )
    return user, password


@pytest.fixture
async def other_program_manager(db_session: AsyncSession, roles_by_name: dict[str, Role]) -> tuple[User, str]:
    password = "OtherManagerSecret123!"
    user = await _create_user(
        db_session,
        roles_by_name,
        email="other.manager@example.com",
        password=password,
        role_names=[PROGRAM_MANAGER],
    )
    return user, password


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    # The suite logs in far more than the production rate limit allows, all from
    # the same in-process, session-wide limiter state - bypass it in tests.
    app.dependency_overrides[login_rate_limiter] = lambda: None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


async def login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
