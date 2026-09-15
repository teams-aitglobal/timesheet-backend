


Python 3.12+, FastAPI, SQLAlchemy 2.x (async, asyncpg), Pydantic v2,
python-jose (JWT), bcrypt, pytest / pytest-asyncio / httpx.

## Key business rule

There is no public registration endpoint. The first `SUPER_ADMIN` is created
via a CLI bootstrap script (`app/scripts/create_superadmin.py`), never over
HTTP. From then on, only users holding `USER_CREATE` may create accounts,
and only `SUPER_ADMIN` may grant the `SUPER_ADMIN` role.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL, SECRET_KEY, etc.

uvicorn app.main:app --reload
# on startup this creates all 7 tables (if missing) and seeds roles/permissions

python -m app.scripts.create_superadmin   # interactive bootstrap of the first SUPER_ADMIN, run once the app has started
```

Swagger UI: `http://localhost:8000/docs`

## Running tests

Tests run against a real PostgreSQL database (SQLite is not used because the
schema relies on native UUID and JSONB types). Point `DATABASE_URL_TEST` in
`.env` at a scratch database, then:

```bash
pytest
```

The test suite creates/drops the schema and seeds roles+permissions once per
session, and truncates the mutable tables (`users`, `user_roles`,
`refresh_tokens`, `audit_logs`) between tests for isolation.

A convenience local Postgres for testing:

```bash
docker run -d --name timesheet-pg -e POSTGRES_USER=timesheet \
  -e POSTGRES_PASSWORD=timesheet -e POSTGRES_MULTIPLE_DATABASES=timesheet,timesheet_test \
  -p 5432:5432 postgres:16
```

(or create `timesheet` and `timesheet_test` databases by hand on any
Postgres 14+ instance).

## Design notes / deliberate decisions

- **Temporary password is returned once, at creation.** Section 17 of the
  spec asks for an invitation/temp-password flow but also says "never return
  the password from the API." Since this phase has no email/invitation
  infrastructure, `POST /api/v1/users` returns the generated temporary
  password exactly once, in the creation response, so the creating admin can
  hand it to the new hire out-of-band. It is never stored in plaintext,
  never logged, and never returned by any other endpoint (`GET /users`,
  `GET /users/{id}`, `/auth/me`, etc. only ever expose `password_hash`-free
  user data). A future phase can replace this with a real invitation-link
  email flow without changing the data model.
- **Role/permission seed catalog lives in `app/db/seed_data.py`** and is
  consumed both by `app.main`'s startup lifespan (so every app boot produces
  a fully seeded database) and by `python -m app.scripts.seed_data` (an
  idempotent manual re-apply, useful if the permission catalog changes
  without restarting the app).
- **No migration tool (Alembic) is used.** `app.main`'s startup lifespan
  calls `Base.metadata.create_all()`, which creates missing tables but never
  alters existing ones (no add/rename/drop column, no type changes). This is
  a deliberate simplicity tradeoff for early development; before this app
  holds real production data, reintroduce a migration tool so schema changes
  can be applied safely.
- **PROJECT_MANAGER / EMPLOYEE permission grants** are a reasonable default
  for their future responsibilities (project/timesheet read & approval for
  PM; timesheet CRUD for EMPLOYEE) even though those endpoints don't exist
  yet in this phase - the permission codes and grants are prepared per
  section 10/30 of the spec, with no enforcement point until Phase 2.
- **`POST /api/v1/users/{id}/roles`** is an additional endpoint (beyond the
  five REST routes explicitly listed) needed to exercise `USER_ROLE_ASSIGN`
  outside of user creation, per section 27's "Assign Role" capability.
- **DELETE /users/{id} deactivates, never deletes**, per section 26.
- Refresh tokens are rotated on every `/auth/refresh` call: the presented
  token is revoked and a new pair is issued.

## Not implemented in this phase

Customers, projects, tasks, project/task assignments, timesheets, timesheet
approvals, notifications. Their permission codes exist (`PROJECT_*`,
`TIMESHEET_*`) but no models, routes, or services back them yet.
