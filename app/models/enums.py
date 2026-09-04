from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ClientStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ClientSpocStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ProjectStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class TaskStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On Hold"
    CANCELLED = "Cancelled"
