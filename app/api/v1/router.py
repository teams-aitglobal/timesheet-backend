from fastapi import APIRouter

from app.api.v1 import (
    auth,
    client_spocs,
    clients,
    dashboard,
    project_assignments,
    projects,
    reports,
    roles,
    task_assignments,
    tasks,
    timesheets,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(clients.router)
api_router.include_router(client_spocs.router)
api_router.include_router(projects.router)
api_router.include_router(project_assignments.router)
api_router.include_router(tasks.router)
api_router.include_router(task_assignments.router)
api_router.include_router(timesheets.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
