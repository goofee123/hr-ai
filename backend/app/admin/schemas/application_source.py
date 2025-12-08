"""Application source schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationSourceCreate(BaseModel):
    """Schema for creating an application source."""

    name: str = Field(..., min_length=1, max_length=100)
    source_type: str = Field(
        default="other",
        description="Source type: job_board, referral, direct, agency, social, other",
    )
    integration_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class ApplicationSourceUpdate(BaseModel):
    """Schema for updating an application source."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_type: Optional[str] = None
    integration_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ApplicationSourceResponse(BaseModel):
    """Schema for application source response."""

    id: UUID
    tenant_id: UUID
    name: str
    source_type: str
    integration_config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
