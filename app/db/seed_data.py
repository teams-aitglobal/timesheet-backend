"""Canonical catalog of seed roles, permissions, and role->permission grants.

Used by the app's startup lifespan (app.main, so every boot produces a fully
seeded database) and by the standalone `app.scripts.seed_data` script (so seed
data can be re-applied manually without restarting the app). Kept as plain
data - no ORM/session code - so both call sites can use it safely.
"""

from app.models.role import EMPLOYEE, PROGRAM_MANAGER, SUPER_ADMIN

ROLES: list[dict] = [
    {"name": SUPER_ADMIN, "description": "Full administrative access. Manages users, roles, and permissions."},
    {
        "name": PROGRAM_MANAGER,
        "description": "Manages projects and employee assignments; reviews and approves timesheets.",
    },
    {"name": EMPLOYEE, "description": "Submits and manages their own timesheets."},
]

# module -> [(code, name, description)]
PERMISSIONS: dict[str, list[tuple[str, str, str]]] = {
    "USERS": [
        ("USER_CREATE", "Create user", "Create a new user account."),
        ("USER_READ", "Read user", "View user accounts."),
        ("USER_UPDATE", "Update user", "Update a user's profile fields."),
        ("USER_DEACTIVATE", "Deactivate user", "Deactivate a user account."),
        ("USER_ROLE_ASSIGN", "Assign user role", "Assign one or more roles to a user."),
        ("USER_PASSWORD_RESET", "Reset user password", "Reset a user's password to a new temporary one."),
    ],
    "ROLES": [
        ("ROLE_READ", "Read role", "View roles."),
        ("ROLE_ASSIGN", "Assign role", "Assign a role to a user."),
    ],
    "CLIENTS": [
        ("CLIENT_CREATE", "Create client", "Create a new client organization."),
        ("CLIENT_READ", "Read client", "View client organizations."),
        ("CLIENT_UPDATE", "Update client", "Update a client organization's details."),
        ("CLIENT_DEACTIVATE", "Deactivate client", "Deactivate a client organization."),
    ],
    "CLIENT_SPOCS": [
        ("CLIENT_SPOC_CREATE", "Create client SPOC", "Create a new client single point of contact."),
        ("CLIENT_SPOC_READ", "Read client SPOC", "View client single points of contact."),
        ("CLIENT_SPOC_UPDATE", "Update client SPOC", "Update a client SPOC's details."),
        ("CLIENT_SPOC_DEACTIVATE", "Deactivate client SPOC", "Deactivate a client SPOC."),
    ],
    "PROJECTS": [
        ("PROJECT_CREATE", "Create project", "Create a new project."),
        ("PROJECT_READ", "Read project", "View projects."),
        ("PROJECT_UPDATE", "Update project", "Update a project's details."),
        ("PROJECT_DEACTIVATE", "Deactivate project", "Deactivate a project."),
        ("PROJECT_ASSIGN_EMPLOYEE", "Assign employee to project", "Assign an employee to a project."),
        ("PROJECT_ASSIGNMENT_READ", "Read project assignment", "View project-employee assignments."),
        ("PROJECT_ASSIGNMENT_UPDATE", "Update project assignment", "Update a project-employee assignment."),
        (
            "PROJECT_ASSIGNMENT_DEACTIVATE",
            "Deactivate project assignment",
            "Deactivate a project-employee assignment.",
        ),
    ],
    "TASKS": [
        ("TASK_CREATE", "Create task", "Create a new task under a project."),
        ("TASK_READ", "Read task", "View tasks."),
        ("TASK_UPDATE", "Update task", "Update a task's details."),
        ("TASK_CANCEL", "Cancel task", "Cancel a task."),
        ("TASK_ASSIGN_EMPLOYEE", "Assign employee to task", "Assign an employee to a task."),
        ("TASK_ASSIGNMENT_READ", "Read task assignment", "View task-employee assignments."),
        ("TASK_ASSIGNMENT_UPDATE", "Update task assignment", "Update a task-employee assignment."),
        ("TASK_ASSIGNMENT_DEACTIVATE", "Deactivate task assignment", "Deactivate a task-employee assignment."),
    ],
    "TIMESHEETS": [
        ("TIMESHEET_CREATE", "Create timesheet", "Create a draft timesheet entry for yourself."),
        ("TIMESHEET_READ", "Read timesheet", "View timesheet entries."),
        ("TIMESHEET_UPDATE", "Update timesheet", "Edit or discard your own draft/rejected timesheet entries."),
        ("TIMESHEET_SUBMIT", "Submit timesheet", "Submit a timesheet entry for approval."),
        ("TIMESHEET_APPROVE", "Approve timesheet", "Approve a submitted timesheet entry."),
        ("TIMESHEET_REJECT", "Reject timesheet", "Reject a submitted timesheet entry with a reason."),
    ],
}

# role name -> [permission codes]
# All codes below are enforced today by app/api/v1/clients.py, app/api/v1/
# projects.py, app/api/v1/project_assignments.py, app/api/v1/tasks.py,
# app/api/v1/task_assignments.py, and app/api/v1/timesheets.py.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    SUPER_ADMIN: [
        "USER_CREATE",
        "USER_READ",
        "USER_UPDATE",
        "USER_DEACTIVATE",
        "USER_ROLE_ASSIGN",
        "USER_PASSWORD_RESET",
        "ROLE_READ",
        "ROLE_ASSIGN",
        "CLIENT_CREATE",
        "CLIENT_READ",
        "CLIENT_UPDATE",
        "CLIENT_DEACTIVATE",
        "CLIENT_SPOC_CREATE",
        "CLIENT_SPOC_READ",
        "CLIENT_SPOC_UPDATE",
        "CLIENT_SPOC_DEACTIVATE",
        "PROJECT_CREATE",
        "PROJECT_READ",
        "PROJECT_UPDATE",
        "PROJECT_DEACTIVATE",
        "PROJECT_ASSIGN_EMPLOYEE",
        "PROJECT_ASSIGNMENT_READ",
        "PROJECT_ASSIGNMENT_UPDATE",
        "PROJECT_ASSIGNMENT_DEACTIVATE",
        "TASK_CREATE",
        "TASK_READ",
        "TASK_UPDATE",
        "TASK_CANCEL",
        "TASK_ASSIGN_EMPLOYEE",
        "TASK_ASSIGNMENT_READ",
        "TASK_ASSIGNMENT_UPDATE",
        "TASK_ASSIGNMENT_DEACTIVATE",
    ],
    PROGRAM_MANAGER: [
        "USER_READ",
        "ROLE_READ",
        "PROJECT_CREATE",
        "PROJECT_READ",
        "PROJECT_UPDATE",
        "PROJECT_DEACTIVATE",
        "PROJECT_ASSIGN_EMPLOYEE",
        "PROJECT_ASSIGNMENT_READ",
        "PROJECT_ASSIGNMENT_UPDATE",
        "PROJECT_ASSIGNMENT_DEACTIVATE",
        "TASK_CREATE",
        "TASK_READ",
        "TASK_UPDATE",
        "TASK_CANCEL",
        "TASK_ASSIGN_EMPLOYEE",
        "TASK_ASSIGNMENT_READ",
        "TASK_ASSIGNMENT_UPDATE",
        "TASK_ASSIGNMENT_DEACTIVATE",
        "TIMESHEET_READ",
        "TIMESHEET_APPROVE",
        "TIMESHEET_REJECT",
    ],
    EMPLOYEE: [
        "PROJECT_READ",
        "TASK_READ",
        "TIMESHEET_CREATE",
        "TIMESHEET_READ",
        "TIMESHEET_UPDATE",
        "TIMESHEET_SUBMIT",
    ],
}
