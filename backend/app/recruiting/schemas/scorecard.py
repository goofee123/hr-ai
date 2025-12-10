"""Scorecard schemas for structured interviewing."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Scorecard Attribute Types
# =============================================================================

class ScorecardAttribute(BaseModel):
    """Individual attribute/criteria to rate in a scorecard."""

    name: str = Field(..., description="Attribute name, e.g., 'Technical Skills'")
    description: Optional[str] = Field(None, description="What to evaluate")
    required: bool = Field(True, description="Whether rating is required")
    scale_type: str = Field(
        "1-5",
        description="Rating scale type: '1-5', '1-4', 'yes_no', 'strong_no_to_strong_yes'"
    )
    weight: Optional[float] = Field(
        1.0,
        ge=0.1,
        le=5.0,
        description="Relative weight for scoring"
    )


class InterviewQuestion(BaseModel):
    """Question in an interview kit."""

    question: str = Field(..., description="The interview question")
    purpose: Optional[str] = Field(None, description="What this question evaluates")
    follow_ups: Optional[List[str]] = Field(None, description="Suggested follow-up questions")
    expected_signals: Optional[List[str]] = Field(
        None,
        description="Positive/negative signals to look for"
    )


# =============================================================================
# Scorecard Template Schemas
# =============================================================================

class ScorecardTemplateBase(BaseModel):
    """Base fields for scorecard template."""

    name: str = Field(..., min_length=1, max_length=200)
    stage_name: str = Field(..., description="Pipeline stage this applies to")
    description: Optional[str] = None


class ScorecardTemplateCreate(ScorecardTemplateBase):
    """Create a new scorecard template."""

    requisition_id: Optional[UUID] = Field(
        None,
        description="If set, template is specific to this requisition"
    )
    attributes: List[ScorecardAttribute] = Field(
        ...,
        min_length=1,
        description="Rating attributes/criteria"
    )
    interview_questions: Optional[List[InterviewQuestion]] = Field(
        None,
        description="Interview kit questions for this stage"
    )


class ScorecardTemplateUpdate(BaseModel):
    """Update scorecard template."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    attributes: Optional[List[ScorecardAttribute]] = None
    interview_questions: Optional[List[InterviewQuestion]] = None
    is_active: Optional[bool] = None


class ScorecardTemplateResponse(ScorecardTemplateBase):
    """Scorecard template response."""

    id: UUID
    tenant_id: UUID
    requisition_id: Optional[UUID] = None
    attributes: List[ScorecardAttribute]
    interview_questions: Optional[List[InterviewQuestion]] = None
    version: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True


# =============================================================================
# Interview Feedback Schemas
# =============================================================================

class AttributeRating(BaseModel):
    """Rating for a single attribute."""

    attribute_name: str
    score: float = Field(..., description="Numeric score or -1 for N/A")
    notes: Optional[str] = Field(None, description="Notes for this attribute")


class InterviewFeedbackCreate(BaseModel):
    """Submit interview feedback."""

    application_id: UUID
    template_id: UUID
    stage_name: str
    ratings: List[AttributeRating] = Field(
        ...,
        min_length=1,
        description="Ratings for each attribute"
    )
    overall_recommendation: str = Field(
        ...,
        description="strong_yes, yes, no, strong_no, needs_more_info"
    )
    strengths: Optional[List[str]] = Field(None, description="Key strengths observed")
    concerns: Optional[List[str]] = Field(None, description="Concerns or areas to probe")
    notes: Optional[str] = Field(None, description="General interview notes")


class InterviewFeedbackUpdate(BaseModel):
    """Update interview feedback (before submission)."""

    ratings: Optional[List[AttributeRating]] = None
    overall_recommendation: Optional[str] = None
    strengths: Optional[List[str]] = None
    concerns: Optional[List[str]] = None
    notes: Optional[str] = None


class InterviewFeedbackResponse(BaseModel):
    """Interview feedback response."""

    id: UUID
    tenant_id: UUID
    application_id: UUID
    template_id: UUID
    stage_name: str
    interviewer_id: UUID
    ratings: List[AttributeRating]
    overall_recommendation: str
    strengths: Optional[List[str]] = None
    concerns: Optional[List[str]] = None
    notes: Optional[str] = None
    is_submitted: bool = False
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Joined data
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Aggregated Panel View
# =============================================================================

class PanelSummary(BaseModel):
    """Aggregated feedback from all interviewers."""

    application_id: UUID
    stage_name: str
    total_interviewers: int
    submitted_count: int
    pending_count: int

    # Recommendation breakdown
    strong_yes_count: int = 0
    yes_count: int = 0
    no_count: int = 0
    strong_no_count: int = 0
    needs_more_info_count: int = 0

    # Average scores by attribute
    average_scores: dict = Field(
        default_factory=dict,
        description="Average score per attribute name"
    )

    # Overall assessment
    overall_average: Optional[float] = None
    consensus: Optional[str] = Field(
        None,
        description="hire, no_hire, split, pending"
    )

    feedbacks: List[InterviewFeedbackResponse] = Field(
        default_factory=list,
        description="Individual feedback entries"
    )


# =============================================================================
# Interview Kit Response
# =============================================================================

class InterviewKitResponse(BaseModel):
    """Full interview kit for an interviewer."""

    template: ScorecardTemplateResponse
    candidate_name: str
    position_title: str
    stage_name: str
    interview_questions: List[InterviewQuestion]
    existing_feedback: Optional[InterviewFeedbackResponse] = None
    other_feedbacks_summary: Optional[PanelSummary] = None
