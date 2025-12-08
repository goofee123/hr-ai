"""Job requisition schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PipelineStageConfig(BaseModel):
    """Pipeline stage configuration."""

    name: str
    stage_type: str = "standard"
    sort_order: int
    is_rejection_stage: bool = False
    requires_feedback: bool = False
    interview_required: bool = False


class JobRequisitionBase(BaseModel):
    """Base job requisition schema."""

    external_title: str = Field(..., min_length=1, max_length=255)
    internal_title: Optional[str] = None
    internal_title_id: Optional[UUID] = None
    job_description: Optional[str] = None
    requirements: Optional[str] = None
    department_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    reports_to_id: Optional[UUID] = None
    pay_grade_id: Optional[UUID] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    target_salary: Optional[Decimal] = None
    is_salary_visible: bool = False
    positions_approved: int = 1
    worker_type: str = "full_time"
    hiring_manager_id: Optional[UUID] = None
    primary_recruiter_id: Optional[UUID] = None
    target_fill_date: Optional[date] = None
    sla_days: int = 45


class JobRequisitionCreate(JobRequisitionBase):
    """Schema for creating a job requisition."""

    template_id: Optional[UUID] = None
    pipeline_stages: Optional[List[PipelineStageConfig]] = None


class JobRequisitionUpdate(BaseModel):
    """Schema for updating a job requisition."""

    external_title: Optional[str] = Field(None, min_length=1, max_length=255)
    internal_title: Optional[str] = None
    internal_title_id: Optional[UUID] = None
    job_description: Optional[str] = None
    requirements: Optional[str] = None
    department_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    reports_to_id: Optional[UUID] = None
    pay_grade_id: Optional[UUID] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    target_salary: Optional[Decimal] = None
    is_salary_visible: Optional[bool] = None
    positions_approved: Optional[int] = None
    worker_type: Optional[str] = None
    hiring_manager_id: Optional[UUID] = None
    primary_recruiter_id: Optional[UUID] = None
    target_fill_date: Optional[date] = None
    sla_days: Optional[int] = None


class RequisitionStatusUpdate(BaseModel):
    """Schema for updating requisition status."""

    status: str = Field(..., pattern="^(draft|pending_approval|open|on_hold|closed_filled|closed_cancelled)$")
    reason: Optional[str] = None


class PipelineStageCreate(BaseModel):
    """Schema for creating a pipeline stage."""

    name: str = Field(..., min_length=1, max_length=100)
    stage_type: str = "standard"
    sort_order: Optional[int] = None
    is_rejection_stage: bool = False
    requires_feedback: bool = False
    interview_required: bool = False


class PipelineStageUpdate(BaseModel):
    """Schema for updating a pipeline stage."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    stage_type: Optional[str] = None
    sort_order: Optional[int] = None
    is_rejection_stage: Optional[bool] = None
    requires_feedback: Optional[bool] = None
    interview_required: Optional[bool] = None


class PipelineStageResponse(BaseModel):
    """Pipeline stage response."""

    id: UUID
    name: str
    stage_type: str
    sort_order: int
    is_rejection_stage: bool
    requires_feedback: bool
    interview_required: bool
    candidate_count: int = 0

    class Config:
        from_attributes = True


class JobRequisitionResponse(JobRequisitionBase):
    """Schema for job requisition response."""

    id: UUID
    tenant_id: UUID
    requisition_number: str
    status: str
    positions_filled: int
    template_id: Optional[UUID]
    pipeline_stages: Optional[list]
    is_posted_internal: bool
    is_posted_external: bool
    posting_urls: dict
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobRequisitionListResponse(BaseModel):
    """Simplified job requisition for list views."""

    id: UUID
    requisition_number: str
    external_title: str
    department_id: Optional[UUID]
    location_id: Optional[UUID]
    status: str
    positions_approved: int
    positions_filled: int
    worker_type: str
    hiring_manager_id: Optional[UUID]
    primary_recruiter_id: Optional[UUID]
    opened_at: Optional[datetime]
    target_fill_date: Optional[date]
    sla_days: int
    candidate_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
