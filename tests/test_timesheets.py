from datetime import date, timedelta

from httpx import AsyncClient

from .conftest import auth_header, login

_WORK_DATE = "2026-01-06"


async def _create_client_org(client: AsyncClient, headers: dict) -> str:
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
        json={"project_id": project_id, "task_name": "Design homepage", "start_date": "2026-01-05"},
        headers=headers,
    )
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


async def _setup_project_with_task(
    client: AsyncClient, admin_headers: dict, manager_id: str, employee_id: str
) -> tuple[str, str]:
    client_id = await _create_client_org(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager_id)
    task_id = await _create_task(client, admin_headers, project_id)
    await _assign_to_project(client, admin_headers, project_id, employee_id)
    await _assign_to_task(client, admin_headers, task_id, employee_id)
    return project_id, task_id


def _assigned_task_payload(project_id: str, task_id: str, **overrides) -> dict:
    payload = {
        "work_date": _WORK_DATE,
        "project_id": project_id,
        "work_type": "Assigned Task",
        "task_id": task_id,
        "hours": 4.0,
        "work_description": "Implemented homepage layout.",
    }
    payload.update(overrides)
    return payload


async def test_employee_creates_and_submits_timesheet(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["timesheet_status"] == "Draft"
    assert body["employee_id"] == worker.employee_id
    timesheet_id = body["timesheet_id"]

    submit_response = await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)
    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["timesheet_status"] == "Submitted"
    assert submit_response.json()["submitted_at"] is not None


async def test_adhoc_work_type_rejects_task_id(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.post(
        "/api/v1/timesheets",
        json={
            "work_date": _WORK_DATE,
            "project_id": project_id,
            "work_type": "Adhoc",
            "task_id": task_id,
            "hours": 2.0,
            "work_description": "Should fail.",
        },
        headers=worker_headers,
    )
    assert response.status_code == 422


async def test_adhoc_entry_without_task_id_succeeds(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, _ = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.post(
        "/api/v1/timesheets",
        json={
            "work_date": _WORK_DATE,
            "project_id": project_id,
            "work_type": "Meeting",
            "hours": 1.0,
            "work_description": "Sprint planning.",
        },
        headers=worker_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["task_id"] is None


async def test_cannot_log_time_against_unassigned_task(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    client_id = await _create_client_org(client, admin_headers)
    project_id = await _create_project(client, admin_headers, client_id, manager.employee_id)
    task_id = await _create_task(client, admin_headers, project_id)
    await _assign_to_project(client, admin_headers, project_id, worker.employee_id)
    # Note: worker is NOT assigned to the task itself.

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    assert response.status_code == 403


async def test_daily_hours_cannot_exceed_24(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    first = await client.post(
        "/api/v1/timesheets",
        json=_assigned_task_payload(project_id, task_id, hours=20.0),
        headers=worker_headers,
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/timesheets",
        json={
            "work_date": _WORK_DATE,
            "project_id": project_id,
            "work_type": "Meeting",
            "hours": 5.0,
            "work_description": "Status call.",
        },
        headers=worker_headers,
    )
    assert second.status_code == 422


async def test_future_work_date_rejected(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])

    future_date = (date.today() + timedelta(days=1)).isoformat()
    response = await client.post(
        "/api/v1/timesheets",
        json=_assigned_task_payload(project_id, task_id, work_date=future_date),
        headers=worker_headers,
    )
    assert response.status_code == 422


async def test_full_reject_and_resubmit_flow(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, manager_password = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    manager_tokens = await login(client, manager.email, manager_password)
    manager_headers = auth_header(manager_tokens["access_token"])

    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)

    reject_response = await client.post(
        f"/api/v1/timesheets/{timesheet_id}/reject",
        json={"rejection_reason": "Hours exceed the estimate; please confirm."},
        headers=manager_headers,
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["timesheet_status"] == "Rejected"
    assert reject_response.json()["rejection_reason"]

    # Employee edits the rejected entry.
    update_response = await client.patch(
        f"/api/v1/timesheets/{timesheet_id}", json={"hours": 3.0}, headers=worker_headers
    )
    assert update_response.status_code == 200, update_response.text

    resubmit_response = await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)
    assert resubmit_response.status_code == 200
    assert resubmit_response.json()["timesheet_status"] == "Submitted"
    assert resubmit_response.json()["rejection_reason"] is None

    approve_response = await client.post(
        f"/api/v1/timesheets/{timesheet_id}/approve", headers=manager_headers
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["timesheet_status"] == "Approved"
    assert approve_response.json()["approved_by"] == manager.employee_id


async def test_approved_timesheet_is_immutable(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, manager_password = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    manager_tokens = await login(client, manager.email, manager_password)
    manager_headers = auth_header(manager_tokens["access_token"])

    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)
    await client.post(f"/api/v1/timesheets/{timesheet_id}/approve", headers=manager_headers)

    update_response = await client.patch(
        f"/api/v1/timesheets/{timesheet_id}", json={"hours": 1.0}, headers=worker_headers
    )
    assert update_response.status_code == 422


async def test_other_employee_cannot_edit_or_submit_someone_elses_timesheet(
    client: AsyncClient, super_admin, program_manager, employee, other_employee
):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    other, other_password = other_employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]

    other_tokens = await login(client, other.email, other_password)
    other_headers = auth_header(other_tokens["access_token"])

    response = await client.patch(
        f"/api/v1/timesheets/{timesheet_id}", json={"hours": 1.0}, headers=other_headers
    )
    assert response.status_code == 403


async def test_unrelated_program_manager_cannot_approve(
    client: AsyncClient, super_admin, program_manager, employee, other_program_manager
):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    other_manager, other_manager_password = other_program_manager
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)

    other_manager_tokens = await login(client, other_manager.email, other_manager_password)
    other_manager_headers = auth_header(other_manager_tokens["access_token"])

    response = await client.post(f"/api/v1/timesheets/{timesheet_id}/approve", headers=other_manager_headers)
    assert response.status_code == 403


async def test_pending_approval_scoped_to_managers_projects(
    client: AsyncClient, super_admin, program_manager, employee
):
    admin, admin_password = super_admin
    manager, manager_password = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)

    manager_tokens = await login(client, manager.email, manager_password)
    manager_headers = auth_header(manager_tokens["access_token"])
    response = await client.get("/api/v1/timesheets/pending-approval", headers=manager_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["total_hours"] == 4.0


async def test_employee_cannot_approve_own_timesheet(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]
    await client.post(f"/api/v1/timesheets/{timesheet_id}/submit", headers=worker_headers)

    response = await client.post(f"/api/v1/timesheets/{timesheet_id}/approve", headers=worker_headers)
    assert response.status_code == 403


async def test_discard_draft_timesheet(client: AsyncClient, super_admin, program_manager, employee):
    admin, admin_password = super_admin
    manager, _ = program_manager
    worker, worker_password = employee
    admin_tokens = await login(client, admin.email, admin_password)
    admin_headers = auth_header(admin_tokens["access_token"])
    project_id, task_id = await _setup_project_with_task(client, admin_headers, manager.employee_id, worker.employee_id)

    worker_tokens = await login(client, worker.email, worker_password)
    worker_headers = auth_header(worker_tokens["access_token"])
    create_response = await client.post(
        "/api/v1/timesheets", json=_assigned_task_payload(project_id, task_id), headers=worker_headers
    )
    timesheet_id = create_response.json()["timesheet_id"]

    delete_response = await client.delete(f"/api/v1/timesheets/{timesheet_id}", headers=worker_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/timesheets/{timesheet_id}", headers=worker_headers)
    assert get_response.status_code == 404
