from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ClientStatus


class ClientCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    industry: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ClientUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    industry: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: ClientStatus | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    client_name: str
    email: str | None
    phone: str | None
    industry: str | None
    description: str | None
    status: ClientStatus
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None
