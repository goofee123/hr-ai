"""EEO (Equal Employment Opportunity) compliance schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# EEO Response Categories (OFCCP/EEOC compliant)
class GenderOptions:
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class EthnicityOptions:
    HISPANIC_LATINO = "hispanic_or_latino"
    WHITE = "white"
    BLACK_AFRICAN_AMERICAN = "black_or_african_american"
    NATIVE_AMERICAN = "native_american_or_alaska_native"
    ASIAN = "asian"
    NATIVE_HAWAIIAN = "native_hawaiian_or_pacific_islander"
    TWO_OR_MORE = "two_or_more_races"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class VeteranStatusOptions:
    PROTECTED_VETERAN = "protected_veteran"
    NOT_PROTECTED_VETERAN = "not_protected_veteran"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class DisabilityStatusOptions:
    YES = "yes"
    NO = "no"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


# Request/Response Schemas
class EEOResponseCreate(BaseModel):
    """Schema for submitting EEO self-identification."""
    application_id: UUID
    gender: Optional[str] = Field(None, description="Gender identity")
    ethnicity: Optional[str] = Field(None, description="Race/Ethnicity")
    veteran_status: Optional[str] = Field(None, description="Veteran status")
    disability_status: Optional[str] = Field(None, description="Disability status")


class EEOResponseResponse(BaseModel):
    """Schema for EEO response record."""
    id: UUID
    application_id: UUID
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    veteran_status: Optional[str] = None
    disability_status: Optional[str] = None
    collected_at: datetime

    class Config:
        from_attributes = True


class EEOFormOptions(BaseModel):
    """Available options for EEO form (for frontend dropdown population)."""
    gender_options: list[dict] = [
        {"value": "male", "label": "Male"},
        {"value": "female", "label": "Female"},
        {"value": "non_binary", "label": "Non-Binary"},
        {"value": "prefer_not_to_say", "label": "I prefer not to say"},
    ]
    ethnicity_options: list[dict] = [
        {"value": "hispanic_or_latino", "label": "Hispanic or Latino"},
        {"value": "white", "label": "White (Not Hispanic or Latino)"},
        {"value": "black_or_african_american", "label": "Black or African American (Not Hispanic or Latino)"},
        {"value": "native_american_or_alaska_native", "label": "American Indian or Alaska Native (Not Hispanic or Latino)"},
        {"value": "asian", "label": "Asian (Not Hispanic or Latino)"},
        {"value": "native_hawaiian_or_pacific_islander", "label": "Native Hawaiian or Other Pacific Islander (Not Hispanic or Latino)"},
        {"value": "two_or_more_races", "label": "Two or More Races (Not Hispanic or Latino)"},
        {"value": "prefer_not_to_say", "label": "I prefer not to say"},
    ]
    veteran_status_options: list[dict] = [
        {"value": "protected_veteran", "label": "I identify as one or more of the classifications of protected veteran"},
        {"value": "not_protected_veteran", "label": "I am not a protected veteran"},
        {"value": "prefer_not_to_say", "label": "I prefer not to say"},
    ]
    disability_status_options: list[dict] = [
        {"value": "yes", "label": "Yes, I have a disability (or previously had a disability)"},
        {"value": "no", "label": "No, I do not have a disability"},
        {"value": "prefer_not_to_say", "label": "I prefer not to say"},
    ]


# Report Schemas
class EEOSummaryByCategory(BaseModel):
    """Summary counts for a single category value."""
    value: str
    label: str
    count: int
    percentage: float


class EEOCategorySummary(BaseModel):
    """Summary for an entire category (e.g., all gender responses)."""
    category: str
    total_responses: int
    breakdown: list[EEOSummaryByCategory]


class EEOSummaryReport(BaseModel):
    """Full EEO summary report."""
    report_date: datetime
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    total_applications: int
    total_eeo_responses: int
    response_rate: float
    gender_summary: EEOCategorySummary
    ethnicity_summary: EEOCategorySummary
    veteran_summary: EEOCategorySummary
    disability_summary: EEOCategorySummary


class AdverseImpactAnalysis(BaseModel):
    """Adverse impact analysis for a specific stage transition."""
    stage_from: str
    stage_to: str
    group_name: str
    group_applicants: int
    group_selected: int
    group_selection_rate: float
    reference_group: str
    reference_selection_rate: float
    impact_ratio: float  # group_rate / reference_rate
    four_fifths_rule_pass: bool  # True if ratio >= 0.8


class AdverseImpactReport(BaseModel):
    """Full adverse impact report."""
    report_date: datetime
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    requisition_id: Optional[UUID] = None
    analyses: list[AdverseImpactAnalysis]
    warnings: list[str]  # List of potential adverse impact warnings


# Audit Log Schemas
class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    id: UUID
    tenant_id: UUID
    action_type: str
    entity_type: str
    entity_id: UUID
    user_id: UUID
    action_data: dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int
