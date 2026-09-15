from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TaskStatus


class TaskCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=50)
    task_name: str = Field(min_length=1, max_length=200)
    task_description: str | None = Field(default=None, max_length=500)
    planned_hours: float | None = Field(default=None, ge=0)
    start_date: date
    due_date: date | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "TaskCreate":
        if self.due_date is not None and self.due_date < self.start_date:
            raise ValueError("due_date cannot be before start_date.")
        return self


class TaskUpdate(BaseModel):
    task_name: str | None = Field(default=None, min_length=1, max_length=200)
    task_description: str | None = Field(default=None, max_length=500)
    planned_hours: float | None = Field(default=None, ge=0)
    start_date: date | None = None
    due_date: date | None = None
    status: TaskStatus | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "TaskUpdate":
        if self.start_date is not None and self.due_date is not None and self.due_date < self.start_date:
            raise ValueError("due_date cannot be before start_date.")
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    project_id: str
    task_name: str
    task_description: str | None
    planned_hours: float | None
    start_date: date
    due_date: date | None
    status: TaskStatus
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None


class MyTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    project_id: str
    task_assignment_id: str
    task_name: str
    task_description: str | None
    planned_hours: float | None
    start_date: date
    due_date: date | None
    status: TaskStatus


class MyTaskStatusUpdate(BaseModel):
    status: TaskStatus
