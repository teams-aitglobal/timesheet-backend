from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ClientStatus


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String, primary_key=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status", native_enum=False, create_constraint=True, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ClientStatus.ACTIVE,
        server_default=ClientStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.employee_id"), nullable=False, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.employee_id"), nullable=True, index=True)
