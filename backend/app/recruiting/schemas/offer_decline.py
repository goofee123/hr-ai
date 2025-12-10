"""Offer decline reason schemas for tracking why candidates decline offers."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OfferDeclineReason(BaseModel):
    """Standard offer decline reasons."""

    code: str
    label: str
    category: str = Field(..., description="compensation, opportunity, personal, other")
    description: Optional[str] = None


# Standard decline reasons for analytics
STANDARD_DECLINE_REASONS = [
    # Compensation related
    OfferDeclineReason(
        code="salary_too_low",
        label="Salary Below Expectations",
        category="compensation",
        description="Base salary did not meet candidate's expectations"
    ),
    OfferDeclineReason(
        code="better_comp_elsewhere",
        label="Better Compensation Elsewhere",
        category="compensation",
        description="Candidate received higher offer from another company"
    ),
    OfferDeclineReason(
        code="bonus_insufficient",
        label="Bonus/Equity Insufficient",
        category="compensation",
        description="Variable compensation or equity was not competitive"
    ),
    OfferDeclineReason(
        code="benefits_insufficient",
        label="Benefits Not Competitive",
        category="compensation",
        description="Health, retirement, or other benefits were lacking"
    ),

    # Opportunity related
    OfferDeclineReason(
        code="accepted_counter",
        label="Accepted Counter Offer",
        category="opportunity",
        description="Candidate accepted counter-offer from current employer"
    ),
    OfferDeclineReason(
        code="better_role_elsewhere",
        label="Better Role Elsewhere",
        category="opportunity",
        description="Found more appealing role at another company"
    ),
    OfferDeclineReason(
        code="career_growth_concerns",
        label="Career Growth Concerns",
        category="opportunity",
        description="Concerns about advancement opportunities"
    ),
    OfferDeclineReason(
        code="role_mismatch",
        label="Role Not as Expected",
        category="opportunity",
        description="Job responsibilities differed from expectations"
    ),
    OfferDeclineReason(
        code="company_culture",
        label="Company Culture Fit",
        category="opportunity",
        description="Did not feel aligned with company culture"
    ),

    # Personal reasons
    OfferDeclineReason(
        code="location_issue",
        label="Location/Commute",
        category="personal",
        description="Work location or commute was not acceptable"
    ),
    OfferDeclineReason(
        code="relocation_unwilling",
        label="Unwilling to Relocate",
        category="personal",
        description="Not willing to move to required location"
    ),
    OfferDeclineReason(
        code="remote_preference",
        label="Remote Work Preference",
        category="personal",
        description="Wanted more remote work flexibility"
    ),
    OfferDeclineReason(
        code="timing_issue",
        label="Timing Not Right",
        category="personal",
        description="Personal timing issues prevented acceptance"
    ),
    OfferDeclineReason(
        code="family_reasons",
        label="Family Reasons",
        category="personal",
        description="Family circumstances affected decision"
    ),

    # Other
    OfferDeclineReason(
        code="no_response",
        label="No Response/Ghosted",
        category="other",
        description="Candidate stopped responding"
    ),
    OfferDeclineReason(
        code="other",
        label="Other",
        category="other",
        description="Reason not listed (see notes)"
    ),
]


class OfferDeclineReasonCreate(BaseModel):
    """Record why an offer was declined."""

    offer_id: UUID
    reason_code: str = Field(..., description="Code from standard decline reasons")
    secondary_reason_code: Optional[str] = Field(
        None,
        description="Optional secondary reason"
    )
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Additional context from candidate"
    )
    competing_company: Optional[str] = Field(
        None,
        max_length=200,
        description="Company candidate went to (if known)"
    )
    competing_salary: Optional[float] = Field(
        None,
        description="Competing offer salary (if known)"
    )
    would_consider_future: Optional[bool] = Field(
        None,
        description="Would candidate consider future opportunities"
    )
    follow_up_date: Optional[str] = Field(
        None,
        description="Date to follow up with candidate (ISO date)"
    )


class OfferDeclineReasonResponse(BaseModel):
    """Offer decline reason response."""

    id: UUID
    tenant_id: UUID
    offer_id: UUID
    reason_code: str
    secondary_reason_code: Optional[str] = None
    notes: Optional[str] = None
    competing_company: Optional[str] = None
    competing_salary: Optional[float] = None
    would_consider_future: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    created_at: datetime
    recorded_by: UUID

    # Derived fields
    reason_label: Optional[str] = None
    reason_category: Optional[str] = None

    class Config:
        from_attributes = True


class DeclineReasonsListResponse(BaseModel):
    """Available decline reasons."""

    reasons: List[OfferDeclineReason]


class DeclineAnalytics(BaseModel):
    """Analytics on offer decline reasons."""

    period_start: datetime
    period_end: datetime
    total_declines: int

    # By reason
    by_reason: dict = Field(
        default_factory=dict,
        description="Count per reason code"
    )

    # By category
    by_category: dict = Field(
        default_factory=dict,
        description="Count per category"
    )

    # Top reasons
    top_reasons: List[dict] = Field(
        default_factory=list,
        description="Ordered list of most common reasons"
    )

    # Competing companies (if tracked)
    competing_companies: List[dict] = Field(
        default_factory=list,
        description="Companies candidates went to"
    )

    # Average competing salary differential
    avg_salary_differential: Optional[float] = None

    # Re-engagement opportunity
    future_consideration_rate: Optional[float] = Field(
        None,
        description="% of declines open to future contact"
    )
