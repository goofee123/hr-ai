"""User-related schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = "employee"
    employee_id: Optional[str] = None
    department_id: Optional[UUID] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = None
    employee_id: Optional[str] = None
    department_id: Optional[UUID] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    preferences: Optional[dict] = None


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    employee_id: Optional[str]
    department_id: Optional[UUID]
    avatar_url: Optional[str]
    phone: Optional[str]
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
