from httpx import AsyncClient

from .conftest import auth_header, login


async def _create_client(client: AsyncClient, headers: dict) -> str:
    response = await client.post("/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


async def _create_project(client: AsyncClient, headers: dict, client_id: str, manager_id: str) -> str:
    response = await client.post(
        "/api/v1/projects",
        json={
            "project_name": "Website Revamp",
            "client_id": client_id,
            "project_manager_id": manager_id,
            "project_start_date": "2026-01-01",
            "project_end_date": "2026-06-30",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["project_id"]


def _task_payload(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "task_name": "Design homepage",
        "task_description": "Create wireframes and visual design for the homepage.",
        "planned_hours": 40,
        "start_date": "2026-01-05",
        "due_date": "2026-01-20",
    }


async def test_super_admin_creates_task(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["task_name"] == "Design homepage"
    assert body["project_id"] == project_id
    assert body["planned_hours"] == 40
    assert body["status"] == "Not Started"
    assert body["task_id"]


async def test_create_task_for_nonexistent_project_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post("/api/v1/tasks", json=_task_payload("PRJ9999"), headers=headers)
    assert response.status_code == 404


async def test_create_task_due_date_before_start_date_rejected(
    client: AsyncClient, super_admin, program_manager
):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    payload = _task_payload(project_id)
    payload["due_date"] = "2026-01-01"

    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 422


async def test_unauthenticated_task_creation_rejected(client: AsyncClient):
    response = await client.post("/api/v1/tasks", json=_task_payload("PRJ0001"))
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_task(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post("/api/v1/tasks", json=_task_payload("PRJ0001"), headers=headers)
    assert response.status_code == 403


async def test_employee_can_read_tasks(client: AsyncClient, super_admin, program_manager, employee):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=headers)

    emp_user, emp_password = employee
    emp_tokens = await login(client, emp_user.email, emp_password)
    emp_headers = auth_header(emp_tokens["access_token"])

    response = await client.get(f"/api/v1/tasks?project_id={project_id}", headers=emp_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_list_tasks_paginated(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    for name in ["Design homepage", "Build API", "QA testing"]:
        payload = _task_payload(project_id)
        payload["task_name"] = name
        await client.post("/api/v1/tasks", json=payload, headers=headers)

    response = await client.get(f"/api/v1/tasks?project_id={project_id}&skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_task(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    create_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=headers)
    task_id = create_response.json()["task_id"]

    update_response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "In Progress", "planned_hours": 60},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["status"] == "In Progress"
    assert body["planned_hours"] == 60
    assert body["updated_by"] == admin.employee_id


async def test_cancel_task(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    create_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=headers)
    task_id = create_response.json()["task_id"]

    response = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Cancelled"


async def test_get_nonexistent_task_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/tasks/TSK9999", headers=headers)
    assert response.status_code == 404


async def test_employee_sees_only_their_own_assigned_tasks(
    client: AsyncClient, super_admin, program_manager, employee
):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    client_id = await _create_client(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id)

    mine_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=admin_headers)
    mine_task_id = mine_response.json()["task_id"]
    theirs_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=admin_headers)
    theirs_task_id = theirs_response.json()["task_id"]

    await client.post(
        "/api/v1/task-assignments",
        json={"task_id": mine_task_id, "employee_id": worker.employee_id, "assigned_date": "2026-01-06"},
        headers=admin_headers,
    )

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.get("/api/v1/tasks/me", params={"project_id": project_id}, headers=worker_headers)
    assert response.status_code == 200
    body = response.json()
    task_ids = {t["task_id"] for t in body}
    assert task_ids == {mine_task_id}
    assert theirs_task_id not in task_ids


async def test_employee_can_update_status_of_own_task(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    client_id = await _create_client(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id)

    task_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=admin_headers)
    task_id = task_response.json()["task_id"]
    await client.post(
        "/api/v1/task-assignments",
        json={"task_id": task_id, "employee_id": worker.employee_id, "assigned_date": "2026-01-06"},
        headers=admin_headers,
    )

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.patch(
        f"/api/v1/tasks/me/{task_id}", json={"status": "In Progress"}, headers=worker_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "In Progress"
    assert body["updated_by"] == worker.employee_id


async def test_employee_cannot_update_status_of_unassigned_task(
    client: AsyncClient, super_admin, program_manager, employee
):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    client_id = await _create_client(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id)

    task_response = await client.post("/api/v1/tasks", json=_task_payload(project_id), headers=admin_headers)
    task_id = task_response.json()["task_id"]

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.patch(
        f"/api/v1/tasks/me/{task_id}", json={"status": "In Progress"}, headers=worker_headers
    )
    assert response.status_code == 403
