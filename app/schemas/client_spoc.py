from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ClientSpocStatus = Literal["Active", "Inactive"]


class ClientSpocCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=50)
    client_spoc_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    phone: str = Field(min_length=1, max_length=20)
    designation: str | None = Field(default=None, max_length=100)
    is_primary: bool = False


class ClientSpocUpdate(BaseModel):
    client_spoc_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    designation: str | None = Field(default=None, max_length=100)
    is_primary: bool | None = None
    status: ClientSpocStatus | None = None


class ClientSpocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_spoc_id: str
    client_id: str
    client_spoc_name: str
    email: str
    phone: str
    designation: str | None
    is_primary: bool
    status: str
    created_at: datetime
    created_by: str
    updated_at: datetime | None
    updated_by: str | None
