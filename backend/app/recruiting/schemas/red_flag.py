"""Red Flag / Caution Flag schemas for candidate risk management."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RedFlagType(BaseModel):
    """Standard red flag types."""

    code: str
    label: str
    severity: str = Field(..., description="low, medium, high")
    description: Optional[str] = None


# Standard red flag types
STANDARD_RED_FLAG_TYPES = [
    RedFlagType(
        code="do_not_rehire",
        label="Do Not Rehire",
        severity="high",
        description="Candidate should not be considered for future positions"
    ),
    RedFlagType(
        code="reference_check_failed",
        label="Reference Check Failed",
        severity="high",
        description="Issues discovered during reference verification"
    ),
    RedFlagType(
        code="background_check_issue",
        label="Background Check Issue",
        severity="high",
        description="Problems found in background screening"
    ),
    RedFlagType(
        code="needs_exec_approval",
        label="Needs Executive Approval",
        severity="medium",
        description="Special approval required before advancing"
    ),
    RedFlagType(
        code="salary_mismatch",
        label="Salary Expectations Mismatch",
        severity="low",
        description="Candidate salary expectations exceed budget"
    ),
    RedFlagType(
        code="relocation_required",
        label="Relocation Required",
        severity="low",
        description="Candidate would need to relocate"
    ),
    RedFlagType(
        code="visa_required",
        label="Visa Sponsorship Required",
        severity="medium",
        description="Candidate requires work authorization sponsorship"
    ),
    RedFlagType(
        code="former_employee",
        label="Former Employee",
        severity="low",
        description="Candidate previously worked at company"
    ),
    RedFlagType(
        code="compliance_concern",
        label="Compliance Concern",
        severity="high",
        description="Potential compliance or legal issue"
    ),
    RedFlagType(
        code="behavior_concern",
        label="Behavior Concern",
        severity="medium",
        description="Concerns about professional behavior"
    ),
    RedFlagType(
        code="other",
        label="Other",
        severity="low",
        description="Custom flag with notes"
    ),
]


class RedFlagCreate(BaseModel):
    """Add a red flag to a candidate."""

    candidate_id: UUID
    flag_type: str = Field(
        ...,
        description="Flag type code from standard types or 'other'"
    )
    severity: str = Field(
        "medium",
        description="low, medium, high"
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Explanation for the flag"
    )
    is_blocking: bool = Field(
        False,
        description="If true, prevents advancing candidate without override"
    )
    expiration_date: Optional[str] = Field(
        None,
        description="When flag should auto-expire (ISO date)"
    )


class RedFlagUpdate(BaseModel):
    """Update a red flag."""

    severity: Optional[str] = None
    reason: Optional[str] = Field(None, min_length=10, max_length=2000)
    is_blocking: Optional[bool] = None
    expiration_date: Optional[str] = None
    is_resolved: Optional[bool] = None
    resolution_notes: Optional[str] = Field(None, max_length=1000)


class RedFlagResponse(BaseModel):
    """Red flag response."""

    id: UUID
    tenant_id: UUID
    candidate_id: UUID
    flag_type: str
    severity: str
    reason: str
    is_blocking: bool = False
    is_resolved: bool = False
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    expiration_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    # Joined data
    created_by_name: Optional[str] = None
    resolved_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class RedFlagSummary(BaseModel):
    """Summary of flags for a candidate."""

    candidate_id: UUID
    total_flags: int = 0
    active_flags: int = 0
    resolved_flags: int = 0
    blocking_flags: int = 0

    high_severity_count: int = 0
    medium_severity_count: int = 0
    low_severity_count: int = 0

    flags: List[RedFlagResponse] = Field(default_factory=list)

    has_blocking: bool = False
    most_severe: Optional[str] = None  # high, medium, low, or None


class RedFlagTypesResponse(BaseModel):
    """Available red flag types."""

    types: List[RedFlagType]
