from httpx import AsyncClient

from .conftest import auth_header, login


async def _create_client(client: AsyncClient, headers: dict) -> str:
    response = await client.post(
        "/api/v1/clients", json={"client_name": "Acme Corp"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


async def test_super_admin_creates_client_spoc(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
            "designation": "VP Operations",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["client_id"] == client_id
    assert body["client_spoc_name"] == "Meera Nair"
    assert body["email"] == "meera.nair@acmecorp.com"
    assert body["is_primary"] is False
    assert body["status"] == "Active"
    assert body["client_spoc_id"]


async def test_create_client_spoc_for_nonexistent_client_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": "CLI9999",
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    assert response.status_code == 404


async def test_unauthenticated_client_spoc_creation_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": "CLI0001",
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
    )
    assert response.status_code in (401, 403)


async def test_employee_cannot_create_client_spoc(client: AsyncClient, employee):
    user, password = employee
    tokens = await login(client, user.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": "CLI0001",
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    assert response.status_code == 403


async def test_list_client_spocs_paginated(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    for name in ["Meera Nair", "Rakesh B", "Arjun Kumar"]:
        await client.post(
            "/api/v1/client-spocs",
            json={
                "client_id": client_id,
                "client_spoc_name": name,
                "email": f"{name.split()[0].lower()}@acmecorp.com",
                "phone": "+91-9876543210",
            },
            headers=headers,
        )

    response = await client.get(f"/api/v1/client-spocs?client_id={client_id}&skip=0&limit=2", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_client_spoc(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    create_response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    spoc_id = create_response.json()["client_spoc_id"]

    update_response = await client.patch(
        f"/api/v1/client-spocs/{spoc_id}",
        json={"designation": "CFO", "phone": "+91-9998887770"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["designation"] == "CFO"
    assert body["phone"] == "+91-9998887770"
    assert body["client_spoc_name"] == "Meera Nair"
    assert body["updated_by"] == admin.employee_id


async def test_duplicate_email_for_same_client_rejected(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    payload = {
        "client_id": client_id,
        "client_spoc_name": "Meera Nair",
        "email": "meera.nair@acmecorp.com",
        "phone": "+91-9876543210",
    }
    first = await client.post("/api/v1/client-spocs", json=payload, headers=headers)
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/client-spocs",
        json={**payload, "client_spoc_name": "Meera Duplicate"},
        headers=headers,
    )
    assert second.status_code == 409


async def test_update_client_spoc_email_to_existing_one_rejected(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    first = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Rakesh B",
            "email": "rakesh@acmecorp.com",
            "phone": "+91-9876543211",
        },
        headers=headers,
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["client_spoc_id"]

    update_response = await client.patch(
        f"/api/v1/client-spocs/{second_id}",
        json={"email": "meera.nair@acmecorp.com"},
        headers=headers,
    )
    assert update_response.status_code == 409


async def test_only_one_primary_spoc_per_client(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    first = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
            "is_primary": True,
        },
        headers=headers,
    )
    first_id = first.json()["client_spoc_id"]
    assert first.json()["is_primary"] is True

    second = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Rakesh B",
            "email": "rakesh@acmecorp.com",
            "phone": "+91-9876543211",
            "is_primary": True,
        },
        headers=headers,
    )
    assert second.json()["is_primary"] is True

    refreshed_first = await client.get(f"/api/v1/client-spocs/{first_id}", headers=headers)
    assert refreshed_first.json()["is_primary"] is False


async def test_deactivate_client_spoc(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])
    client_id = await _create_client(client, headers)

    create_response = await client.post(
        "/api/v1/client-spocs",
        json={
            "client_id": client_id,
            "client_spoc_name": "Meera Nair",
            "email": "meera.nair@acmecorp.com",
            "phone": "+91-9876543210",
        },
        headers=headers,
    )
    spoc_id = create_response.json()["client_spoc_id"]

    response = await client.delete(f"/api/v1/client-spocs/{spoc_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Inactive"


async def test_get_nonexistent_client_spoc_returns_404(client: AsyncClient, super_admin):
    admin, password = super_admin
    tokens = await login(client, admin.email, password)
    headers = auth_header(tokens["access_token"])

    response = await client.get("/api/v1/client-spocs/SPOC9999", headers=headers)
    assert response.status_code == 404
