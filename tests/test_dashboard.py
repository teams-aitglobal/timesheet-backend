from datetime import date, timedelta

from httpx import AsyncClient

from .conftest import auth_header, login


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


async def _create_task(
    client: AsyncClient, headers: dict, project_id: str, planned_hours: float | None = None
) -> str:
    payload = {"project_id": project_id, "task_name": "Design homepage", "start_date": "2026-01-05"}
    if planned_hours is not None:
        payload["planned_hours"] = planned_hours
    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["task_id"]


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


async def _assign_to_task(client: AsyncClient, headers: dict, task_id: str, employee_id: str) -> None:
    response = await client.post(
        "/api/v1/task-assignments",
        json={"task_id": task_id, "employee_id": employee_id, "assigned_date": "2026-01-05"},
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def test_employee_dashboard_shape(client: AsyncClient, super_admin, project_manager, employee):
    admin, admin_password = super_admin
    manager, _ = project_manager
    emp, emp_password = employee

    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])

    client_id = await _create_client_org(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id)
    task_id = await _create_task(client, admin_headers, project_id)
    await _assign_to_project(client, admin_headers, project_id, emp.employee_id)
    await _assign_to_task(client, admin_headers, task_id, emp.employee_id)

    emp_tokens = await login(client, emp.email, emp_password)
    emp_headers = auth_header(emp_tokens["access_token"])

    response = await client.get("/api/v1/dashboard", headers=emp_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "EMPLOYEE"
    assert body["active_projects"] == 1
    assert body["remaining_tasks"] == 1
    assert body["draft_timesheets"] == 0
    assert body["projects"][0]["project_id"] == project_id
    assert body["tasks"][0]["task_id"] == task_id


async def test_manager_dashboard_shape(client: AsyncClient, super_admin, project_manager, employee):
    admin, admin_password = super_admin
    manager, manager_password = project_manager
    emp, emp_password = employee

    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])

    client_id = await _create_client_org(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id, budget_hours=100)
    task_id = await _create_task(client, admin_headers, project_id, planned_hours=40)
    await _assign_to_project(client, admin_headers, project_id, emp.employee_id)
    await _assign_to_task(client, admin_headers, task_id, emp.employee_id)

    emp_tokens = await login(client, emp.email, emp_password)
    emp_headers = auth_header(emp_tokens["access_token"])
    work_date = (date.today() - timedelta(days=1)).isoformat()
    timesheet_response = await client.post(
        "/api/v1/timesheets",
        json={
            "work_date": work_date,
            "project_id": project_id,
            "work_type": "Assigned Task",
            "task_id": task_id,
            "hours": 6.0,
            "work_description": "Implemented homepage layout.",
        },
        headers=emp_headers,
    )
    assert timesheet_response.status_code == 201, timesheet_response.text
    timesheet_id = timesheet_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=emp_headers)

    manager_tokens = await login(client, manager.email, manager_password)
    manager_headers = auth_header(manager_tokens["access_token"])
    approve_response = await client.post(f"/api/v1/timesheets/{timesheet_id}/approve", headers=manager_headers)
    assert approve_response.status_code == 200, approve_response.text

    response = await client.get("/api/v1/dashboard", headers=manager_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "PROJECT_MANAGER"
    assert body["my_projects"] == 1
    assert body["clients"] == 1
    assert body["team_members"] == 1
    assert body["pending_approvals"] == 0
    assert body["projects"][0]["project_id"] == project_id
    assert body["projects"][0]["budget_hours"] == 100
    assert body["projects"][0]["hours_logged"] == 6.0


async def test_admin_dashboard_shape(client: AsyncClient, super_admin, project_manager):
    admin, admin_password = super_admin
    manager, _ = project_manager

    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])

    client_id = await _create_client_org(client, admin_headers)
    await _create_project(client, admin_headers, client_id, manager.employee_id)

    response = await client.get("/api/v1/dashboard", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "SUPER_ADMIN"
    assert body["total_clients"] >= 1
    assert body["active_projects"] >= 1
    assert body["total_employees"] >= 1
