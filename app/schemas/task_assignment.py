from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskAssignmentCreate(BaseModel):
    task_id: str = Field(min_length=1, max_length=50)
    employee_id: str = Field(min_length=1, max_length=50)
    assigned_date: date


class TaskAssignmentUpdate(BaseModel):
    assigned_date: date | None = None
    is_active: bool | None = None


class TaskAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_assignment_id: str
    project_id: str
    task_id: str
    employee_id: str
    assigned_date: date
    is_active: bool
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None
