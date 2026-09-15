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


def _assignment_payload(project_id: str, employee_id: str) -> dict:
    return {
        "project_id": project_id,
        "employee_id": employee_id,
        "allocated_hours": 20,
        "start_date": "2026-01-05",
        "end_date": "2026-03-31",
        "remarks": "Initial allocation.",
    }


async def test_super_admin_creates_project_assignment(client: AsyncClient, super_admin, project_manager, employee):
    admin, password = super_admin
    manager, _ = project_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload(project_id, worker.employee_id),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] == project_id
    assert body["employee_id"] == worker.employee_id
    assert body["allocated_hours"] == 20
    assert body["is_active"] is True
    assert body["project_assignment_id"]


async def test_create_assignment_for_nonexistent_project_returns_404(
    client: AsyncClient, super_admin, employee
):
    admin, password = super_admin
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload("PRJ9999", worker.employee_id),
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_assignment_for_nonexistent_employee_returns_404(
    client: AsyncClient, super_admin, project_manager
):
    admin, password = super_admin
    manager, _ = project_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload(project_id, "EMP9999"),
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_assignment_end_date_before_start_date_rejected(
    client: AsyncClient, super_admin, project_manager, employee
):
    admin, password = super_admin
    manager, _ = project_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    payload = _assignment_payload(project_id, worker.employee_id)
    payload["end_date"] = "2025-12-31"

    response = await client.post("/api/v1/project-assignments", json=payload, headers=headers)
    assert response.status_code == 422


async def test_unauthenticated_assignment_creation_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload("PRJ0001", "EMP0001"),
    )
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_assignment(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload("PRJ0001", "EMP0001"),
        headers=headers,
    )
    assert response.status_code == 403


async def test_list_project_assignments_paginated(
    client: AsyncClient, super_admin, project_manager, employee
):
    admin, password = super_admin
    manager, _ = project_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    for hours in [10, 20, 30]:
        payload = _assignment_payload(project_id, worker.employee_id)
        payload["allocated_hours"] = hours
        await client.post("/api/v1/project-assignments", json=payload, headers=headers)

    response = await client.get(
        f"/api/v1/project-assignments?project_id={project_id}&skip=0&limit=2", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_project_assignment(client: AsyncClient, super_admin, project_manager, employee):
    admin, password = super_admin
    manager, _ = project_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    create_response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload(project_id, worker.employee_id),
        headers=headers,
    )
    assignment_id = create_response.json()["project_assignment_id"]

    update_response = await client.patch(
        f"/api/v1/project-assignments/{assignment_id}",
        json={"allocated_hours": 40, "remarks": "Increased allocation."},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["allocated_hours"] == 40
    assert body["remarks"] == "Increased allocation."
    assert body["updated_by"] == admin.employee_id


async def test_deactivate_project_assignment(client: AsyncClient, super_admin, project_manager, employee):
    admin, password = super_admin
    manager, _ = project_manager
    worker, _ = employee
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    project_id = await _create_project(client, headers, client_id, manager.employee_id)

    create_response = await client.post(
        "/api/v1/project-assignments",
        json=_assignment_payload(project_id, worker.employee_id),
        headers=headers,
    )
    assignment_id = create_response.json()["project_assignment_id"]

    response = await client.delete(f"/api/v1/project-assignments/{assignment_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_get_nonexistent_project_assignment_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/project-assignments/PA9999", headers=headers)
    assert response.status_code == 404
