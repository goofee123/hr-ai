"""Tenant settings schemas for feature toggles and configuration."""

from datetime import datetime
from typing import Dict, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class CandidatePortalSettings(BaseModel):
    """Settings for the candidate portal feature."""
    enabled: bool = Field(
        default=False,
        description="Enable/disable candidate portal (disable if using external system like Dayforce)"
    )
    allow_status_check: bool = Field(
        default=True,
        description="Allow candidates to check application status"
    )
    allow_document_upload: bool = Field(
        default=True,
        description="Allow candidates to upload additional documents"
    )
    allow_interview_reschedule: bool = Field(
        default=True,
        description="Allow candidates to reschedule interviews via portal"
    )
    require_eeo_form: bool = Field(
        default=True,
        description="Show EEO self-identification form to candidates"
    )
    custom_branding: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom branding for portal (logo_url, primary_color, etc.)"
    )
    portal_url_slug: Optional[str] = Field(
        default=None,
        description="Custom URL slug for the portal (e.g., 'careers' -> /careers/status)"
    )


class CalendarIntegrationSettings(BaseModel):
    """Settings for calendar integrations."""
    enabled: bool = Field(default=False)
    google_calendar_enabled: bool = Field(default=False)
    outlook_calendar_enabled: bool = Field(default=False)
    auto_create_video_meeting: bool = Field(
        default=True,
        description="Automatically create Google Meet/Teams link for video interviews"
    )


class NotificationSettings(BaseModel):
    """Settings for email and notification preferences."""
    send_candidate_status_emails: bool = Field(default=True)
    send_interview_reminders: bool = Field(default=True)
    reminder_hours_before: list = Field(default=[24, 1])
    send_offer_emails: bool = Field(default=True)
    send_rejection_emails: bool = Field(default=False)
    rejection_email_delay_hours: int = Field(
        default=48,
        description="Hours to wait before sending rejection emails"
    )


class AIFeatureSettings(BaseModel):
    """Settings for AI/ML features."""
    resume_parsing_enabled: bool = Field(default=True)
    candidate_matching_enabled: bool = Field(default=True)
    skill_extraction_enabled: bool = Field(default=True)
    auto_screen_candidates: bool = Field(
        default=False,
        description="Automatically screen candidates based on rules"
    )


class ComplianceSettings(BaseModel):
    """Settings for compliance features."""
    eeo_tracking_enabled: bool = Field(default=True)
    audit_logging_enabled: bool = Field(default=True)
    require_rejection_reason: bool = Field(default=True)
    data_retention_days: int = Field(
        default=365,
        description="Days to retain candidate data after application closure"
    )


class TenantSettingsUpdate(BaseModel):
    """Update tenant settings."""
    candidate_portal: Optional[CandidatePortalSettings] = None
    calendar_integration: Optional[CalendarIntegrationSettings] = None
    notifications: Optional[NotificationSettings] = None
    ai_features: Optional[AIFeatureSettings] = None
    compliance: Optional[ComplianceSettings] = None
    custom_settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional custom settings as key-value pairs"
    )


class TenantSettingsResponse(BaseModel):
    """Full tenant settings response."""
    id: UUID
    tenant_id: UUID
    candidate_portal: CandidatePortalSettings = Field(default_factory=CandidatePortalSettings)
    calendar_integration: CalendarIntegrationSettings = Field(default_factory=CalendarIntegrationSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    ai_features: AIFeatureSettings = Field(default_factory=AIFeatureSettings)
    compliance: ComplianceSettings = Field(default_factory=ComplianceSettings)
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
