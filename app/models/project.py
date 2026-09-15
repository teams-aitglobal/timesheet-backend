from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ProjectStatus


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.client_id"), nullable=False, index=True)
    project_manager_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_id"), nullable=False, index=True
    )
    client_spoc_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("client_spocs.client_spoc_id"), nullable=True, index=True
    )
    project_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    project_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    project_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    budget_hours: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, create_constraint=True, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ProjectStatus.ACTIVE,
        server_default=ProjectStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.employee_id"), nullable=True, index=True)
