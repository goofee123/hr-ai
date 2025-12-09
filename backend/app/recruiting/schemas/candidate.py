"""Candidate schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CandidateBase(BaseModel):
    """Base candidate schema."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[dict] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    referred_by_id: Optional[UUID] = None
    worker_type_preference: Optional[str] = None
    skills: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class CandidateCreate(CandidateBase):
    """Schema for creating a candidate."""

    is_internal_candidate: bool = False
    current_employee_id: Optional[UUID] = None


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[dict] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    worker_type_preference: Optional[str] = None
    skills: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_do_not_contact: Optional[bool] = None


class ResumeResponse(BaseModel):
    """Resume response."""

    id: UUID
    file_name: str
    file_path: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    version_number: int
    is_primary: bool
    parsing_status: str
    parsed_data: dict
    uploaded_at: datetime

    class Config:
        from_attributes = True


class CandidateResponse(CandidateBase):
    """Schema for candidate response."""

    id: UUID
    tenant_id: UUID
    is_internal_candidate: bool
    current_employee_id: Optional[UUID]
    is_do_not_contact: bool
    total_applications: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CandidateDetailResponse(CandidateResponse):
    """Detailed candidate response with resumes."""

    resumes: List[ResumeResponse] = []

    class Config:
        from_attributes = True


class CandidateSearchResult(BaseModel):
    """Candidate search result."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    source: Optional[str]
    skills: Optional[List[str]]
    tags: Optional[List[str]]
    total_applications: int
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateApplicationHistory(BaseModel):
    """Application history for a candidate."""

    application_id: UUID
    requisition_id: UUID
    requisition_number: str
    job_title: str
    applied_at: datetime
    current_stage: str
    status: str
    days_in_pipeline: int


class CandidateMatchingJob(BaseModel):
    """A job that matches a candidate's profile."""

    requisition_id: UUID
    requisition_number: str
    job_title: str
    department_name: Optional[str] = None
    location: Optional[str] = None
    match_score: Optional[float] = None  # 0.0 to 1.0
    match_reasons: Optional[List[str]] = None
    job_status: str


class CandidateActivityLog(BaseModel):
    """Activity log entry for a candidate."""

    id: UUID
    activity_type: str  # 'application_submitted', 'stage_change', 'interview_scheduled', 'note_added', etc.
    activity_description: str
    activity_data: Optional[dict] = None
    performed_by: Optional[str] = None  # User name
    occurred_at: datetime


class ConvertToApplicantRequest(BaseModel):
    """Request to convert a candidate to an applicant for a job."""

    requisition_id: UUID = Field(..., description="Job requisition to apply for")
    source: Optional[str] = Field(None, description="Application source override")
    notes: Optional[str] = Field(None, description="Notes about the application")
