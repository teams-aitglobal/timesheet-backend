from datetime import date, timedelta

from httpx import AsyncClient

from .conftest import auth_header, login

_WORK_DATE = (date.today() - timedelta(days=1)).isoformat()


async def _create_client_org(client: AsyncClient, headers: dict) -> str:
    response = await client.post("/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


async def _create_project(
    client: AsyncClient, headers: dict, client_id: str, manager_id: str, budget_hours: float | None = None
) -> str:
    payload = {
        "project_name": "Website Revamp",
        "client_id": client_id,
        "project_manager_id": manager_id,
        "project_start_date": "2026-01-01",
    }
    if budget_hours is not None:
        payload["budget_hours"] = budget_hours
    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["project_id"]


async def _assign_to_project(client: AsyncClient, headers: dict, project_id: str, employee_id: str) -> None:
    response = await client.post(
        "/api/v1/project-assignments",
        json={
            "project_id": project_id,
            "employee_id": employee_id,
            "allocated_hours": 40,
            "start_date": "2026-01-01",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _create_submitted_timesheet(
    client: AsyncClient, employee_headers: dict, project_id: str, hours: float = 4.0
) -> str:
    create_response = await client.post(
        "/api/v1/timesheets",
        json={
            "work_date": _WORK_DATE,
            "project_id": project_id,
            "work_type": "Adhoc",
            "hours": hours,
            "work_description": "Worked on the homepage.",
        },
        headers=employee_headers,
    )
    assert create_response.status_code == 201, create_response.text
    timesheet_id = create_response.json()["timesheet_id"]
    submit_response = await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=employee_headers)
    assert submit_response.status_code == 200, submit_response.text
    return timesheet_id


async def _setup(client: AsyncClient, super_admin, project_manager, employee, budget_hours: float | None = None):
    admin, admin_password = super_admin
    manager, manager_password = project_manager
    emp, emp_password = employee

    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])

    client_id = await _create_client_org(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id, budget_hours)
    await _assign_to_project(client, admin_headers, project_id, emp.employee_id)

    emp_tokens = await login(client, emp.email, emp_password)
    emp_headers = auth_header(emp_tokens["access_token"])
    manager_tokens = await login(client, manager.email, manager_password)
    manager_headers = auth_header(manager_tokens["access_token"])

    return project_id, admin_headers, manager_headers, emp_headers


async def test_employee_timesheet_report_scoped_to_self(client: AsyncClient, super_admin, project_manager, employee):
    project_id, _, _, emp_headers = await _setup(client, super_admin, project_manager, employee)
    timesheet_id = await _create_submitted_timesheet(client, emp_headers, project_id)

    response = await client.get("/api/v1/reports/timesheets", headers=emp_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["timesheet_id"] == timesheet_id
    assert body["items"][0]["project_name"] == "Website Revamp"


async def test_manager_timesheet_report_sees_own_projects(client: AsyncClient, super_admin, project_manager, employee):
    project_id, _, manager_headers, emp_headers = await _setup(client, super_admin, project_manager, employee)
    await _create_submitted_timesheet(client, emp_headers, project_id)

    response = await client.get("/api/v1/reports/timesheets", headers=manager_headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


async def test_timesheet_report_csv_export(client: AsyncClient, super_admin, project_manager, employee):
    project_id, _, _, emp_headers = await _setup(client, super_admin, project_manager, employee)
    await _create_submitted_timesheet(client, emp_headers, project_id)

    response = await client.get("/api/v1/reports/timesheets", params={"format": "csv"}, headers=emp_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "Website Revamp" in response.text


async def test_project_hours_report_includes_approved_hours(
    client: AsyncClient, super_admin, project_manager, employee
):
    project_id, admin_headers, manager_headers, emp_headers = await _setup(
        client, super_admin, project_manager, employee, budget_hours=100
    )
    timesheet_id = await _create_submitted_timesheet(client, emp_headers, project_id, hours=6.0)
    approve_response = await client.post(f"/api/v1/timesheets/{timesheet_id}/approve", headers=manager_headers)
    assert approve_response.status_code == 200, approve_response.text

    response = await client.get("/api/v1/reports/project-hours", headers=manager_headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["project_id"] == project_id
    assert rows[0]["hours_logged"] == 6.0
    assert rows[0]["remaining_hours"] == 94.0


async def test_project_hours_report_forbidden_for_employee(client: AsyncClient, super_admin, project_manager, employee):
    _, _, _, emp_headers = await _setup(client, super_admin, project_manager, employee)

    response = await client.get("/api/v1/reports/project-hours", headers=emp_headers)
    assert response.status_code == 403
