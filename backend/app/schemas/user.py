"""User request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    """User data returned to clients."""

    id: int
    email: str | None
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """User creation payload."""

    email: EmailStr
    password: str
    full_name: str
    role: str = "consumer"
