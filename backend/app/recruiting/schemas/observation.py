"""Schemas for candidate observations, emails, and activity events."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# VALUE TYPES
# =============================================================================

class ValueType:
    """Observation value types."""
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    ARRAY = "array"


class ExtractionMethod:
    """Methods for extracting observations."""
    LLM = "llm"
    MANUAL = "manual"
    LINKEDIN = "linkedin"
    FORM = "form"
    IMPORT = "import"


class EventType:
    """Activity event types."""
    PROFILE_VIEWED = "profile_viewed"
    RESUME_DOWNLOADED = "resume_downloaded"
    RESUME_UPLOADED = "resume_uploaded"
    NOTE_ADDED = "note_added"
    NOTE_EDITED = "note_edited"
    STAGE_CHANGED = "stage_changed"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    REJECTED = "rejected"
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    MERGED = "merged"
    SOURCE_CHANGED = "source_changed"


# =============================================================================
# CANDIDATE EMAIL SCHEMAS
# =============================================================================

class CandidateEmailBase(BaseModel):
    """Base schema for candidate email."""
    email: str = Field(..., max_length=255)
    is_primary: bool = False
    source: Optional[str] = Field(None, max_length=100)


class CandidateEmailCreate(CandidateEmailBase):
    """Schema for creating a candidate email."""
    pass


class CandidateEmailUpdate(BaseModel):
    """Schema for updating a candidate email."""
    is_primary: Optional[bool] = None
    source: Optional[str] = Field(None, max_length=100)


class CandidateEmailResponse(CandidateEmailBase):
    """Schema for candidate email response."""
    id: UUID
    candidate_id: UUID
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# CANDIDATE OBSERVATION SCHEMAS
# =============================================================================

class ObservationBase(BaseModel):
    """Base schema for candidate observation."""
    field_name: str = Field(..., max_length=100)
    field_value: str
    value_type: str = Field(default=ValueType.STRING, max_length=50)
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    extraction_method: Optional[str] = Field(None, max_length=50)

    @field_validator("value_type")
    @classmethod
    def validate_value_type(cls, v: str) -> str:
        valid_types = [ValueType.STRING, ValueType.NUMBER, ValueType.DATE, ValueType.BOOLEAN, ValueType.ARRAY]
        if v not in valid_types:
            raise ValueError(f"value_type must be one of: {valid_types}")
        return v

    @field_validator("extraction_method")
    @classmethod
    def validate_extraction_method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_methods = [ExtractionMethod.LLM, ExtractionMethod.MANUAL, ExtractionMethod.LINKEDIN, ExtractionMethod.FORM, ExtractionMethod.IMPORT]
        if v not in valid_methods:
            raise ValueError(f"extraction_method must be one of: {valid_methods}")
        return v


class ObservationCreate(ObservationBase):
    """Schema for creating an observation."""
    source_document_id: Optional[UUID] = None


class ObservationBulkCreate(BaseModel):
    """Schema for bulk creating observations (e.g., from LLM extraction)."""
    observations: list[ObservationCreate]


class ObservationUpdate(BaseModel):
    """Schema for updating an observation (creates new version, supersedes old)."""
    field_value: Optional[str] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    extraction_method: Optional[str] = Field(None, max_length=50)


class ObservationResponse(ObservationBase):
    """Schema for observation response."""
    id: UUID
    candidate_id: UUID
    source_document_id: Optional[UUID] = None
    superseded_by_id: Optional[UUID] = None
    is_current: bool = True
    extracted_at: datetime
    extracted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObservationSummary(BaseModel):
    """Summarized observation for candidate profile."""
    field_name: str
    field_value: str
    value_type: str
    confidence: Optional[Decimal] = None
    extraction_method: Optional[str] = None
    extracted_at: datetime


# =============================================================================
# ACTIVITY EVENT SCHEMAS
# =============================================================================

class ActivityEventBase(BaseModel):
    """Base schema for activity event."""
    event_type: str = Field(..., max_length=100)
    application_id: Optional[UUID] = None
    event_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        # Allow any event type for flexibility, but warn if not in standard list
        return v


class ActivityEventCreate(ActivityEventBase):
    """Schema for creating an activity event."""
    pass


class ActivityEventResponse(ActivityEventBase):
    """Schema for activity event response."""
    id: UUID
    candidate_id: UUID
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityEventSummary(BaseModel):
    """Summary of activity event for feeds."""
    event_type: str
    user_id: Optional[UUID] = None
    event_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# =============================================================================
# AGGREGATED SCHEMAS
# =============================================================================

class CandidateObservationsResponse(BaseModel):
    """All current observations for a candidate, grouped by field."""
    candidate_id: UUID
    observations: dict[str, ObservationSummary]  # field_name -> observation
    total_count: int
    last_extracted_at: Optional[datetime] = None


class CandidateActivityFeed(BaseModel):
    """Activity feed for a candidate."""
    candidate_id: UUID
    events: list[ActivityEventSummary]
    total_count: int
    has_more: bool


class CandidateEmailsResponse(BaseModel):
    """All emails for a candidate."""
    candidate_id: UUID
    emails: list[CandidateEmailResponse]
    primary_email: Optional[str] = None


# =============================================================================
# LLM EXTRACTION SCHEMAS
# =============================================================================

class ExtractedFact(BaseModel):
    """Single fact extracted from a document by LLM."""
    field: str
    value: str
    confidence: Decimal = Field(..., ge=0, le=1)


class LLMExtractionResult(BaseModel):
    """Result of LLM extraction from a document."""
    document_id: UUID
    facts: list[ExtractedFact]
    model_used: str
    extraction_time_ms: int
    raw_response: Optional[str] = None
