from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ClientSpocStatus


class ClientSpoc(Base):
    __tablename__ = "client_spocs"
    __table_args__ = (UniqueConstraint("client_id", "email", name="uq_client_spocs_client_id_email"),)

    client_spoc_id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.client_id"), nullable=False, index=True)
    client_spoc_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[ClientSpocStatus] = mapped_column(
        Enum(ClientSpocStatus, name="client_spoc_status", native_enum=False, create_constraint=True, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ClientSpocStatus.ACTIVE,
        server_default=ClientSpocStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.employee_id"), nullable=True, index=True)
