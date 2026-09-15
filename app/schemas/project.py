from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=50)
    project_manager_id: str = Field(min_length=1, max_length=50)
    client_spoc_id: str | None = Field(default=None, max_length=50)
    project_start_date: date
    project_end_date: date | None = None
    project_description: str | None = Field(default=None, max_length=500)
    budget_hours: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_dates(self) -> "ProjectCreate":
        if self.project_end_date is not None and self.project_end_date < self.project_start_date:
            raise ValueError("project_end_date cannot be before project_start_date.")
        return self


class ProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_manager_id: str | None = Field(default=None, min_length=1, max_length=50)
    client_spoc_id: str | None = Field(default=None, max_length=50)
    project_start_date: date | None = None
    project_end_date: date | None = None
    project_description: str | None = Field(default=None, max_length=500)
    budget_hours: float | None = Field(default=None, ge=0)
    status: ProjectStatus | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "ProjectUpdate":
        if (
            self.project_start_date is not None
            and self.project_end_date is not None
            and self.project_end_date < self.project_start_date
        ):
            raise ValueError("project_end_date cannot be before project_start_date.")
        return self


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_name: str
    client_id: str
    project_manager_id: str
    client_spoc_id: str | None
    project_start_date: date
    project_end_date: date | None
    project_description: str | None
    budget_hours: float | None
    status: ProjectStatus
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None
