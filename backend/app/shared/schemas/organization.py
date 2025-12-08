"""Organization structure schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Department schemas
class DepartmentBase(BaseModel):
    """Base department schema."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    cost_center: Optional[str] = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    """Schema for creating a department."""

    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating a department."""

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    cost_center: Optional[str] = None
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    """Schema for department response."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Location schemas
class LocationBase(BaseModel):
    """Base location schema."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[dict] = None
    timezone: str = "America/New_York"
    is_remote: bool = False
    is_active: bool = True


class LocationCreate(LocationBase):
    """Schema for creating a location."""

    pass


class LocationUpdate(BaseModel):
    """Schema for updating a location."""

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[dict] = None
    timezone: Optional[str] = None
    is_remote: Optional[bool] = None
    is_active: Optional[bool] = None


class LocationResponse(LocationBase):
    """Schema for location response."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Pay Grade schemas
class PayGradeBase(BaseModel):
    """Base pay grade schema."""

    code: str = Field(..., min_length=1, max_length=50)
    name: Optional[str] = None
    min_hourly: Optional[Decimal] = None
    mid_hourly: Optional[Decimal] = None
    max_hourly: Optional[Decimal] = None
    min_annual: Optional[Decimal] = None
    mid_annual: Optional[Decimal] = None
    max_annual: Optional[Decimal] = None
    sort_order: int = 0
    is_active: bool = True
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class PayGradeCreate(PayGradeBase):
    """Schema for creating a pay grade."""

    pass


class PayGradeUpdate(BaseModel):
    """Schema for updating a pay grade."""

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = None
    min_hourly: Optional[Decimal] = None
    mid_hourly: Optional[Decimal] = None
    max_hourly: Optional[Decimal] = None
    min_annual: Optional[Decimal] = None
    mid_annual: Optional[Decimal] = None
    max_annual: Optional[Decimal] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class PayGradeResponse(PayGradeBase):
    """Schema for pay grade response."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
