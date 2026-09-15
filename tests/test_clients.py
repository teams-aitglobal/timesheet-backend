from httpx import AsyncClient

from .conftest import auth_header, login


async def test_super_admin_creates_client(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/clients",
        json={"client_name": "Acme Corp", "email": "meera.nair@acmecorp.com"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["client_name"] == "Acme Corp"
    assert body["email"] == "meera.nair@acmecorp.com"
    assert body["status"] == "Active"
    assert body["client_id"]


async def test_unauthenticated_client_creation_rejected(client: AsyncClient):
    response = await client.post("/api/v1/clients", json={"client_name": "Acme Corp"})
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_client(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post("/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers)
    assert response.status_code == 403


async def test_project_manager_can_manage_clients(client: AsyncClient, project_manager):
    user, password = project_manager
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    create_response = await client.post(
        "/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers
    )
    assert create_response.status_code == 201, create_response.text

    list_response = await client.get("/api/v1/clients", headers=headers)
    assert list_response.status_code == 200


async def test_list_clients_paginated(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    for name in ["Acme Corp", "Initech", "Umbrella Ltd"]:
        await client.post("/api/v1/clients", json={"client_name": name}, headers=headers)

    response = await client.get("/api/v1/clients?skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["skip"] == 0
    assert body["limit"] == 2


async def test_update_client(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    create_response = await client.post(
        "/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers
    )
    client_id = create_response.json()["client_id"]

    update_response = await client.patch(
        f"/api/v1/clients/{client_id}",
        json={"email": "meera.nair@acmecorp.com", "industry": "Manufacturing"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["email"] == "meera.nair@acmecorp.com"
    assert body["industry"] == "Manufacturing"
    assert body["client_name"] == "Acme Corp"
    assert body["updated_by"] == admin.employee_id


async def test_deactivate_client(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    create_response = await client.post(
        "/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers
    )
    client_id = create_response.json()["client_id"]

    response = await client.delete(f"/api/v1/clients/{client_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Inactive"


async def test_get_nonexistent_client_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/clients/CLI9999", headers=headers)
    assert response.status_code == 404
