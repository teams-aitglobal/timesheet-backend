import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserStatus = Literal["Active", "Inactive"]


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    designation_id: str | None = Field(default=None, max_length=100)
    date_of_joining: date | None = None
    description: str | None = Field(default=None, max_length=500)
    role_ids: list[uuid.UUID] = Field(min_length=1)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    designation_id: str | None = Field(default=None, max_length=100)
    date_of_joining: date | None = None
    description: str | None = Field(default=None, max_length=500)
    status: UserStatus | None = None


class RoleAssignRequest(BaseModel):
    role_ids: list[uuid.UUID] = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: str
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    designation_id: str | None
    date_of_joining: date | None
    description: str | None
    status: str
    is_verified: bool
    must_change_password: bool
    created_at: datetime
    created_by: str | None
    updated_at: datetime | None
    updated_by: str | None
    roles: list[str] = Field(default_factory=list)


class UserCreateResponse(UserOut):
    # Returned exactly once, at creation time, so the administrator can hand it to
    # the new user out-of-band. It is never persisted, logged, or returned again by
    # any other endpoint.
    temporary_password: str


class PasswordResetResponse(BaseModel):
    # Returned exactly once, at reset time, so the administrator can hand it to
    # the user out-of-band. It is never persisted, logged, or returned again.
    employee_id: str
    temporary_password: str
