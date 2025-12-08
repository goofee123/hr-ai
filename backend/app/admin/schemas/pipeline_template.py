"""Pipeline template schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PipelineStageConfig(BaseModel):
    """Configuration for a pipeline stage."""

    name: str = Field(..., min_length=1, max_length=100)
    stage_type: str = Field(
        default="standard",
        description="Stage type: initial, screen, interview, offer, hired, rejected",
    )
    sort_order: int = Field(default=0, ge=0)
    is_rejection_stage: bool = Field(default=False)
    requires_feedback: bool = Field(default=False)
    interview_required: bool = Field(default=False)
    auto_advance_days: Optional[int] = Field(
        default=None, description="Auto-advance after N days (optional)"
    )


class PipelineTemplateCreate(BaseModel):
    """Schema for creating a pipeline template."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_default: bool = Field(default=False)
    stages: List[PipelineStageConfig] = Field(default_factory=list)


class PipelineTemplateUpdate(BaseModel):
    """Schema for updating a pipeline template."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    stages: Optional[List[PipelineStageConfig]] = None


class PipelineTemplateResponse(BaseModel):
    """Schema for pipeline template response."""

    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    is_default: bool
    stages: List[dict]  # Raw JSONB from database
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    model_config = {"from_attributes": True}
