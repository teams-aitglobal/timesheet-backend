from httpx import AsyncClient

from .conftest import auth_header, login


async def _create_client(client: AsyncClient, headers: dict) -> str:
    response = await client.post("/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


async def _create_client_spoc(client: AsyncClient, headers: dict, client_id: str) -> str:
    response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["client_spoc_id"]


def _project_payload(client_id: str, manager_id: str, spoc_id: str | None = None) -> dict:
    payload = {
        "project_name": "Website Revamp",
        "client_id": client_id,
        "project_manager_id": manager_id,
        "project_start_date": "2026-01-01",
        "project_end_date": "2026-06-30",
        "project_description": "Rebuild the marketing site.",
        "budget_hours": 500,
    }
    if spoc_id is not None:
        payload["client_spoc_id"] = spoc_id
    return payload


async def test_super_admin_creates_project(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    spoc_id = await _create_client_spoc(client, headers, client_id)

    response = await client.post(
        "/api/v1/projects",
        json=_project_payload(client_id, manager.employee_id, spoc_id),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_name"] == "Website Revamp"
    assert body["client_id"] == client_id
    assert body["project_manager_id"] == manager.employee_id
    assert body["client_spoc_id"] == spoc_id
    assert body["status"] == "Active"
    assert body["project_id"]


async def test_create_project_for_nonexistent_client_returns_404(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/projects",
        json=_project_payload("CLI9999", manager.employee_id),
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_project_for_nonexistent_manager_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    response = await client.post(
        "/api/v1/projects",
        json=_project_payload(client_id, "EMP9999"),
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_project_with_spoc_from_other_client_returns_422(
    client: AsyncClient, super_admin, program_manager
):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)
    other_client_id = await _create_client(client, headers)
    other_spoc_id = await _create_client_spoc(client, headers, other_client_id)

    response = await client.post(
        "/api/v1/projects",
        json=_project_payload(client_id, manager.employee_id, other_spoc_id),
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_project_end_date_before_start_date_rejected(
    client: AsyncClient, super_admin, program_manager
):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    payload = _project_payload(client_id, manager.employee_id)
    payload["project_end_date"] = "2025-12-31"

    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 422


async def test_unauthenticated_project_creation_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/projects",
        json=_project_payload("CLI0001", "EMP0001"),
    )
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_project(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/projects",
        json=_project_payload("CLI0001", "EMP0001"),
        headers=headers,
    )
    assert response.status_code == 403


async def test_list_projects_paginated(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    for name in ["Website Revamp", "Mobile App", "Data Migration"]:
        payload = _project_payload(client_id, manager.employee_id)
        payload["project_name"] = name
        await client.post("/api/v1/projects", json=payload, headers=headers)

    response = await client.get(f"/api/v1/projects?client_id={client_id}&skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_project(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    create_response = await client.post(
        "/api/v1/projects",
        json=_project_payload(client_id, manager.employee_id),
        headers=headers,
    )
    project_id = create_response.json()["project_id"]

    update_response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_name": "Website Revamp v2", "budget_hours": 750},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["project_name"] == "Website Revamp v2"
    assert body["budget_hours"] == 750
    assert body["updated_by"] == admin.employee_id


async def test_deactivate_project(client: AsyncClient, super_admin, program_manager):
    admin, password = super_admin
    manager, _ = program_manager
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    create_response = await client.post(
        "/api/v1/projects",
        json=_project_payload(client_id, manager.employee_id),
        headers=headers,
    )
    project_id = create_response.json()["project_id"]

    response = await client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Inactive"


async def test_get_nonexistent_project_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/projects/PRJ9999", headers=headers)
    assert response.status_code == 404
