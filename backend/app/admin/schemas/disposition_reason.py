"""Disposition reason schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DispositionReasonCreate(BaseModel):
    """Schema for creating a disposition reason."""

    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_eeo_compliant: bool = Field(default=True)
    requires_notes: bool = Field(default=False)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class DispositionReasonUpdate(BaseModel):
    """Schema for updating a disposition reason."""

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_eeo_compliant: Optional[bool] = None
    requires_notes: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class DispositionReasonResponse(BaseModel):
    """Schema for disposition reason response."""

    id: UUID
    tenant_id: UUID
    code: str
    label: str
    description: Optional[str] = None
    is_eeo_compliant: bool
    requires_notes: bool
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
