from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus


class ProjectAssignmentCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=50)
    employee_id: str = Field(min_length=1, max_length=50)
    allocated_hours: float = Field(gt=0)
    start_date: date
    end_date: date | None = None
    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_dates(self) -> "ProjectAssignmentCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date.")
        return self


class ProjectAssignmentUpdate(BaseModel):
    allocated_hours: float | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_dates(self) -> "ProjectAssignmentUpdate":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date cannot be before start_date.")
        return self


class ProjectAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_assignment_id: str
    project_id: str
    employee_id: str
    allocated_hours: float
    start_date: date
    end_date: date | None
    is_active: bool
    remarks: str | None
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None


class MyProjectAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_assignment_id: str
    project_id: str
    project_name: str
    project_status: ProjectStatus
    project_start_date: date
    project_end_date: date | None
    allocated_hours: float
    start_date: date
    end_date: date | None
    is_active: bool
    remarks: str | None
