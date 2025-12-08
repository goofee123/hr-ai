"""Application schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    """Schema for creating an application."""

    candidate_id: UUID
    requisition_id: UUID
    resume_id: Optional[UUID] = None
    cover_letter: Optional[str] = None
    screening_answers: Optional[dict] = None
    assigned_recruiter_id: Optional[UUID] = None


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    resume_id: Optional[UUID] = None
    cover_letter: Optional[str] = None
    screening_answers: Optional[dict] = None
    recruiter_rating: Optional[int] = Field(None, ge=1, le=5)
    hiring_manager_rating: Optional[int] = Field(None, ge=1, le=5)
    assigned_recruiter_id: Optional[UUID] = None


class ApplicationStageUpdate(BaseModel):
    """Schema for updating application stage."""

    stage: str = Field(..., min_length=1, max_length=100)
    stage_id: Optional[UUID] = None
    notes: Optional[str] = None


class ApplicationReject(BaseModel):
    """Schema for rejecting an application."""

    rejection_reason: str = Field(..., min_length=1, max_length=255)
    rejection_notes: Optional[str] = None


class ApplicationEventResponse(BaseModel):
    """Application event response."""

    id: UUID
    event_type: str
    event_data: dict
    performed_by: Optional[UUID]
    performed_at: datetime
    is_internal: bool

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    """Schema for application response."""

    id: UUID
    tenant_id: UUID
    candidate_id: UUID
    requisition_id: UUID
    status: str
    current_stage: str
    current_stage_id: Optional[UUID]
    stage_entered_at: datetime
    resume_id: Optional[UUID]
    cover_letter: Optional[str]
    screening_answers: dict
    recruiter_rating: Optional[int]
    hiring_manager_rating: Optional[int]
    overall_score: Optional[Decimal]
    rejection_reason: Optional[str]
    rejection_notes: Optional[str]
    rejected_by: Optional[UUID]
    rejected_at: Optional[datetime]
    offer_id: Optional[UUID]
    assigned_recruiter_id: Optional[UUID]
    applied_at: datetime
    last_activity_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApplicationWithCandidateResponse(ApplicationResponse):
    """Application response with candidate details."""

    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str]

    class Config:
        from_attributes = True


class PipelineCandidate(BaseModel):
    """Candidate in pipeline view."""

    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    current_stage: str
    stage_entered_at: datetime
    applied_at: datetime
    source: Optional[str]
    recruiter_rating: Optional[int]
    hiring_manager_rating: Optional[int]
    days_in_stage: int

    class Config:
        from_attributes = True


class PipelineStageWithCandidates(BaseModel):
    """Pipeline stage with candidates."""

    id: UUID
    name: str
    stage_type: str
    sort_order: int
    candidate_count: int
    candidates: List[PipelineCandidate]

    class Config:
        from_attributes = True


class PipelineResponse(BaseModel):
    """Full pipeline response."""

    requisition_id: UUID
    requisition_number: str
    external_title: str
    total_candidates: int
    stages: List[PipelineStageWithCandidates]

    class Config:
        from_attributes = True
