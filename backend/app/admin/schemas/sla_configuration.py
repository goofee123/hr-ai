"""SLA configuration schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SLAConfigurationCreate(BaseModel):
    """Schema for creating an SLA configuration."""

    name: str = Field(..., min_length=1, max_length=100)
    job_type: str = Field(
        default="standard",
        description="Job type: standard, executive, urgent, intern, contractor",
    )
    job_sla_days: int = Field(
        default=30, ge=1, le=365, description="Days from opening to fill"
    )
    recruiter_sla_days: int = Field(
        default=14, ge=1, le=365, description="Days for recruiter to show progress"
    )
    amber_threshold_percent: int = Field(
        default=75, ge=1, le=100, description="Alert at this percentage of SLA elapsed"
    )
    red_threshold_percent: int = Field(
        default=90, ge=1, le=100, description="Critical at this percentage of SLA elapsed"
    )
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)


class SLAConfigurationUpdate(BaseModel):
    """Schema for updating an SLA configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    job_type: Optional[str] = None
    job_sla_days: Optional[int] = Field(None, ge=1, le=365)
    recruiter_sla_days: Optional[int] = Field(None, ge=1, le=365)
    amber_threshold_percent: Optional[int] = Field(None, ge=1, le=100)
    red_threshold_percent: Optional[int] = Field(None, ge=1, le=100)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class SLAConfigurationResponse(BaseModel):
    """Schema for SLA configuration response."""

    id: UUID
    tenant_id: UUID
    name: str
    job_type: str
    job_sla_days: int
    recruiter_sla_days: int
    amber_threshold_percent: int
    red_threshold_percent: int
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
