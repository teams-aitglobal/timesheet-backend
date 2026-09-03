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
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["project_id"]


async def _create_task(client: AsyncClient, headers: dict, project_id: str) -> str:
    response = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "task_name": "Design homepage",
            "start_date": "2026-01-05",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["task_id"]


def _assignment_payload(task_id: str, employee_id: str) -> dict:
    return {
        "task_id": task_id,
        "employee_id": employee_id,
        "assigned_date": "2026-01-06",
    }


async def test_super_admin_creates_task_assignment(client: AsyncClient, super_admin, program_manager, employee):
    admin, password = super_admin
    manager, _ = program_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    task_id = await _create_task(client, headers, project_id)

    response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload(task_id, worker.employee_id),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["task_id"] == task_id
    assert body["employee_id"] == worker.employee_id
    assert body["assigned_date"] == "2026-01-06"
    assert body["is_active"] is True
    assert body["task_assignment_id"]


async def test_create_assignment_for_nonexistent_task_returns_404(client: AsyncClient, super_admin, employee):
    admin, password = super_admin
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload("TSK9999", worker.employee_id),
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_assignment_for_nonexistent_employee_returns_404(
    client: AsyncClient, super_admin, program_manager
):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    task_id = await _create_task(client, headers, project_id)

    response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload(task_id, "EMP9999"),
        headers=headers,
    )
    assert response.status_code == 404


async def test_unauthenticated_task_assignment_creation_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload("TSK0001", "EMP0001"),
    )
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_task_assignment(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload("TSK0001", "EMP0001"),
        headers=headers,
    )
    assert response.status_code == 403


async def test_list_task_assignments_paginated(client: AsyncClient, super_admin, program_manager, employee):
    admin, password = super_admin
    manager, _ = program_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    task_a = await _create_task(client, headers, project_id)
    task_b = await _create_task(client, headers, project_id)
    task_c = await _create_task(client, headers, project_id)

    for task_id in [task_a, task_b, task_c]:
        await client.post(
            "/api/v1/task-assignments",
            json=_assignment_payload(task_id, worker.employee_id),
            headers=headers,
        )

    response = await client.get(
        f"/api/v1/task-assignments?employee_id={worker.employee_id}&skip=0&limit=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_task_assignment(client: AsyncClient, super_admin, program_manager, employee):
    admin, password = super_admin
    manager, _ = program_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    task_id = await _create_task(client, headers, project_id)

    create_response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload(task_id, worker.employee_id),
        headers=headers,
    )
    assignment_id = create_response.json()["task_assignment_id"]

    update_response = await client.patch(
        f"/api/v1/task-assignments/{assignment_id}",
        json={"assigned_date": "2026-01-10"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["assigned_date"] == "2026-01-10"
    assert body["updated_by"] == admin.employee_id


async def test_deactivate_task_assignment(client: AsyncClient, super_admin, program_manager, employee):
    admin, password = super_admin
    manager, _ = program_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)
    task_id = await _create_task(client, headers, project_id)

    create_response = await client.post(
        "/api/v1/task-assignments",
        json=_assignment_payload(task_id, worker.employee_id),
        headers=headers,
    )
    assignment_id = create_response.json()["task_assignment_id"]

    response = await client.delete(f"/api/v1/task-assignments/{assignment_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_get_nonexistent_task_assignment_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/task-assignments/TA9999", headers=headers)
    assert response.status_code == 404
