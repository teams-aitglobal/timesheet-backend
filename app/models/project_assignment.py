from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    project_assignment_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.project_id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    allocated_hours: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.employee_id"), nullable=True, index=True)
