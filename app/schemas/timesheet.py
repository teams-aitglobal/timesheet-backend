from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TimesheetStatus, WorkType


class TimesheetCreate(BaseModel):
    work_date: date
    project_id: str = Field(min_length=1, max_length=50)
    work_type: WorkType
    task_id: str | None = Field(default=None, min_length=1, max_length=50)
    hours: float = Field(gt=0, le=24)
    work_description: str = Field(min_length=1, max_length=500)
    employee_comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_task_id(self) -> "TimesheetCreate":
        if self.work_type == WorkType.ASSIGNED_TASK and self.task_id is None:
            raise ValueError("task_id is required when work_type is Assigned Task.")
        if self.work_type != WorkType.ASSIGNED_TASK and self.task_id is not None:
            raise ValueError("task_id must be omitted unless work_type is Assigned Task.")
        return self


class TimesheetUpdate(BaseModel):
    work_date: date | None = None
    project_id: str | None = Field(default=None, min_length=1, max_length=50)
    work_type: WorkType | None = None
    task_id: str | None = Field(default=None, min_length=1, max_length=50)
    hours: float | None = Field(default=None, gt=0, le=24)
    work_description: str | None = Field(default=None, min_length=1, max_length=500)
    employee_comment: str | None = Field(default=None, max_length=500)


class TimesheetReject(BaseModel):
    rejection_reason: str = Field(min_length=1, max_length=500)


class TimesheetBulkAction(BaseModel):
    timesheet_ids: list[str] = Field(min_length=1)


class TimesheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timesheet_id: str
    employee_id: str
    work_date: date
    project_id: str
    work_type: WorkType
    task_id: str | None
    hours: float
    work_description: str
    employee_comment: str | None
    timesheet_status: TimesheetStatus
    rejection_reason: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime | None


class TimesheetBulkActionResult(BaseModel):
    updated: list[TimesheetOut]
    failed: dict[str, str]


class PendingApprovalSummary(BaseModel):
    items: list[TimesheetOut]
    total: int
    total_hours: float
    skip: int
    limit: int
