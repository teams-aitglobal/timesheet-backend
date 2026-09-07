from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TimesheetStatus, WorkType


class Timesheet(Base):
    __tablename__ = "timesheets"
    __table_args__ = (
        # Only ASSIGNED_TASK entries carry a task_id, so this only dedupes those -
        # ADHOC/MEETING rows have a NULL task_id and Postgres treats NULLs as
        # distinct, allowing multiple such entries per employee/day/project.
        UniqueConstraint(
            "employee_id", "work_date", "project_id", "task_id", name="uq_timesheets_employee_date_project_task"
        ),
        CheckConstraint("hours > 0 AND hours <= 24", name="ck_timesheets_hours_range"),
        CheckConstraint(
            "(work_type = 'Assigned Task' AND task_id IS NOT NULL) "
            "OR (work_type != 'Assigned Task' AND task_id IS NULL)",
            name="ck_timesheets_task_id_matches_work_type",
        ),
    )

    timesheet_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.project_id"), nullable=False, index=True)
    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType, name="work_type", native_enum=False, create_constraint=True, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    task_id: Mapped[str | None] = mapped_column(String, ForeignKey("tasks.task_id"), nullable=True, index=True)
    hours: Mapped[float] = mapped_column(Numeric(4, 2, asdecimal=False), nullable=False)
    work_description: Mapped[str] = mapped_column(String(500), nullable=False)
    employee_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timesheet_status: Mapped[TimesheetStatus] = mapped_column(
        Enum(
            TimesheetStatus,
            name="timesheet_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TimesheetStatus.DRAFT,
        server_default=TimesheetStatus.DRAFT.value,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
