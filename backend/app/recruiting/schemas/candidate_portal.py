"""Candidate portal schemas for public-facing candidate interactions."""

from datetime import datetime, date
from typing import Dict, List, Optional, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


# =============================================================================
# Enums
# =============================================================================

class ApplicationStatusPublic(str, Enum):
    """Public-facing application status values."""
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWS_COMPLETE = "interviews_complete"
    DECISION_PENDING = "decision_pending"
    OFFER_EXTENDED = "offer_extended"
    HIRED = "hired"
    NOT_SELECTED = "not_selected"
    WITHDRAWN = "withdrawn"


# =============================================================================
# Magic Link Authentication
# =============================================================================

class PortalAccessRequest(BaseModel):
    """Request access to candidate portal via email."""
    email: EmailStr
    recaptcha_token: Optional[str] = Field(None, description="reCAPTCHA verification token")


class PortalAccessResponse(BaseModel):
    """Response after requesting portal access."""
    message: str = "If an account exists with this email, you will receive an access link shortly."
    email_sent: bool = True


class PortalMagicLinkVerify(BaseModel):
    """Verify a magic link token."""
    token: str


class PortalSession(BaseModel):
    """Candidate portal session after magic link verification."""
    session_token: str
    candidate_id: UUID
    candidate_name: str
    candidate_email: str
    expires_at: datetime


# =============================================================================
# Application Status (Public View)
# =============================================================================

class ApplicationStatusUpdate(BaseModel):
    """A single status update in the timeline."""
    status: str
    title: str
    description: Optional[str] = None
    timestamp: datetime
    is_current: bool = False


class InterviewInfoPublic(BaseModel):
    """Public-facing interview information."""
    id: UUID
    interview_type: str
    title: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: int
    location: Optional[str] = None
    video_link: Optional[str] = None
    status: str
    can_reschedule: bool = False


class ApplicationDetailPublic(BaseModel):
    """Public-facing application details for candidates."""
    id: UUID
    position_title: str
    department: Optional[str] = None
    location: Optional[str] = None
    applied_at: datetime
    current_status: ApplicationStatusPublic
    status_message: str
    status_timeline: List[ApplicationStatusUpdate] = Field(default_factory=list)
    upcoming_interviews: List[InterviewInfoPublic] = Field(default_factory=list)
    documents_requested: List[str] = Field(default_factory=list)
    can_withdraw: bool = True


class ApplicationListPublic(BaseModel):
    """List of applications for a candidate."""
    applications: List[ApplicationDetailPublic]
    total: int


# =============================================================================
# Document Upload
# =============================================================================

class DocumentType(str, Enum):
    """Types of documents candidates can upload."""
    ADDITIONAL_RESUME = "additional_resume"
    COVER_LETTER = "cover_letter"
    PORTFOLIO = "portfolio"
    WORK_SAMPLE = "work_sample"
    REFERENCES = "references"
    TRANSCRIPT = "transcript"
    CERTIFICATION = "certification"
    OTHER = "other"


class DocumentUploadRequest(BaseModel):
    """Request to upload a document."""
    application_id: UUID
    document_type: DocumentType
    filename: str
    content_type: str
    description: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Response with upload URL for document."""
    upload_url: str
    document_id: UUID
    expires_at: datetime


class CandidateDocument(BaseModel):
    """Document uploaded by candidate."""
    id: UUID
    application_id: UUID
    document_type: DocumentType
    filename: str
    file_url: str
    uploaded_at: datetime
    description: Optional[str] = None


# =============================================================================
# EEO Self-Identification
# =============================================================================

class EEOFormOptions(BaseModel):
    """Options for EEO self-identification form."""
    gender_options: List[Dict[str, str]]
    ethnicity_options: List[Dict[str, str]]
    veteran_status_options: List[Dict[str, str]]
    disability_status_options: List[Dict[str, str]]


class EEOSelfIdentification(BaseModel):
    """EEO self-identification submission."""
    application_id: UUID
    gender: Optional[str] = Field(None, description="'male', 'female', 'non_binary', 'prefer_not_to_say'")
    ethnicity: Optional[str] = Field(None, description="Hispanic/Latino, White, Black, Asian, etc.")
    veteran_status: Optional[str] = Field(None, description="'veteran', 'not_veteran', 'prefer_not_to_say'")
    disability_status: Optional[str] = Field(None, description="'yes', 'no', 'prefer_not_to_say'")


class EEOSubmissionResponse(BaseModel):
    """Response after EEO submission."""
    success: bool
    message: str = "Thank you for completing the voluntary self-identification form."


# =============================================================================
# Interview Actions
# =============================================================================

class InterviewConfirmation(BaseModel):
    """Candidate confirming an interview."""
    interview_id: UUID
    confirmed: bool
    notes: Optional[str] = None


class InterviewRescheduleRequest(BaseModel):
    """Candidate requesting to reschedule."""
    interview_id: UUID
    reason: str = Field(..., min_length=10, max_length=500)
    preferred_dates: Optional[List[date]] = Field(None, max_length=5)


class InterviewRescheduleResponse(BaseModel):
    """Response to reschedule request."""
    request_id: UUID
    status: str  # "submitted", "approved", "denied"
    message: str


# =============================================================================
# Withdrawal
# =============================================================================

class WithdrawalRequest(BaseModel):
    """Request to withdraw application."""
    application_id: UUID
    reason: Optional[str] = Field(None, max_length=500)


class WithdrawalResponse(BaseModel):
    """Response to withdrawal request."""
    success: bool
    message: str = "Your application has been withdrawn."


# =============================================================================
# Profile Update
# =============================================================================

class CandidateProfileUpdate(BaseModel):
    """Update candidate profile information."""
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    preferred_location: Optional[str] = None
    willing_to_relocate: Optional[bool] = None


class CandidateProfileResponse(BaseModel):
    """Candidate profile information."""
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    preferred_location: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    active_applications_count: int = 0
