"""Interview scheduling schemas for availability, scheduling, and self-scheduling."""

from datetime import datetime, date, time
from typing import Dict, List, Optional, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, field_validator


# =============================================================================
# Enums
# =============================================================================

class InterviewType(str, Enum):
    """Types of interviews."""
    PHONE = "phone"
    VIDEO = "video"
    ONSITE = "onsite"
    PANEL = "panel"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    FINAL = "final"


class InterviewStatus(str, Enum):
    """Interview status values."""
    PENDING_SLOTS = "pending_slots"  # Waiting for interviewer availability
    PENDING_CANDIDATE = "pending_candidate"  # Waiting for candidate to pick slot
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class AvailabilityStatus(str, Enum):
    """Availability submission status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    EXPIRED = "expired"


class CalendarProvider(str, Enum):
    """Supported calendar integrations."""
    GOOGLE = "google"
    OUTLOOK = "outlook"
    NONE = "none"


# =============================================================================
# Time Slot Schemas
# =============================================================================

class TimeSlot(BaseModel):
    """A single time slot for availability or scheduling."""
    start_time: datetime
    end_time: datetime
    timezone: str = Field(default="America/New_York")

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class DayAvailability(BaseModel):
    """Availability for a single day."""
    date: date
    slots: List[TimeSlot] = Field(default_factory=list)
    is_unavailable: bool = Field(
        default=False,
        description="If true, interviewer is completely unavailable this day"
    )


class WeeklyPattern(BaseModel):
    """Recurring weekly availability pattern."""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    is_available: bool = True


# =============================================================================
# Interviewer Availability Schemas
# =============================================================================

class InterviewerAvailabilityRequest(BaseModel):
    """Request sent to interviewer to submit availability."""
    id: Optional[UUID] = None
    interviewer_id: UUID
    interview_request_id: UUID
    date_range_start: date
    date_range_end: date
    duration_minutes: int = Field(default=60, ge=15, le=480)
    timezone: str = Field(default="America/New_York")
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class InterviewerAvailabilitySubmit(BaseModel):
    """Interviewer submitting their availability."""
    available_slots: List[TimeSlot]
    weekly_patterns: Optional[List[WeeklyPattern]] = None
    notes: Optional[str] = None
    calendar_sync_enabled: bool = False


class InterviewerAvailabilityResponse(BaseModel):
    """Response with interviewer availability details."""
    id: UUID
    interviewer_id: UUID
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None
    interview_request_id: UUID
    date_range_start: date
    date_range_end: date
    duration_minutes: int
    timezone: str
    available_slots: List[TimeSlot] = Field(default_factory=list)
    weekly_patterns: Optional[List[WeeklyPattern]] = None
    status: AvailabilityStatus
    submitted_at: Optional[datetime] = None
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Interview Request Schemas (Internal)
# =============================================================================

class InterviewRequestCreate(BaseModel):
    """Create an interview scheduling request."""
    application_id: UUID
    stage_name: str
    interview_type: InterviewType = InterviewType.VIDEO
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    interviewer_ids: List[UUID] = Field(..., min_length=1)
    preferred_date_range_start: Optional[date] = None
    preferred_date_range_end: Optional[date] = None
    location: Optional[str] = None
    video_link: Optional[str] = None
    notes: Optional[str] = None


class InterviewRequestUpdate(BaseModel):
    """Update an interview request."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    interviewer_ids: Optional[List[UUID]] = None
    preferred_date_range_start: Optional[date] = None
    preferred_date_range_end: Optional[date] = None
    location: Optional[str] = None
    video_link: Optional[str] = None
    notes: Optional[str] = None


class InterviewRequestResponse(BaseModel):
    """Response for an interview scheduling request."""
    id: UUID
    tenant_id: UUID
    application_id: UUID
    stage_name: str
    interview_type: InterviewType
    title: str
    description: Optional[str] = None
    duration_minutes: int
    interviewer_ids: List[UUID]
    preferred_date_range_start: Optional[date] = None
    preferred_date_range_end: Optional[date] = None
    location: Optional[str] = None
    video_link: Optional[str] = None
    notes: Optional[str] = None
    status: InterviewStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    # Joined data
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    position_title: Optional[str] = None
    interviewers: Optional[List[Dict[str, Any]]] = None
    availability_requests: Optional[List[InterviewerAvailabilityResponse]] = None

    class Config:
        from_attributes = True


# =============================================================================
# Interview Scheduling Schemas
# =============================================================================

class InterviewScheduleCreate(BaseModel):
    """Schedule an interview at a specific time."""
    interview_request_id: UUID
    scheduled_at: datetime
    timezone: str = Field(default="America/New_York")
    location: Optional[str] = None
    video_link: Optional[str] = None
    send_calendar_invites: bool = True
    send_candidate_email: bool = True
    custom_message: Optional[str] = None


class InterviewScheduleUpdate(BaseModel):
    """Update a scheduled interview."""
    scheduled_at: Optional[datetime] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    video_link: Optional[str] = None
    status: Optional[InterviewStatus] = None
    notes: Optional[str] = None


class InterviewScheduleResponse(BaseModel):
    """Response for a scheduled interview."""
    id: UUID
    tenant_id: UUID
    application_id: UUID
    interview_request_id: Optional[UUID] = None
    interview_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: int
    timezone: Optional[str] = None
    location: Optional[str] = None
    video_link: Optional[str] = None
    interviewer_ids: Optional[List[UUID]] = None
    organizer_id: Optional[UUID] = None
    status: str
    feedback_due_by: Optional[datetime] = None
    all_feedback_received: bool = False
    calendar_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Joined data
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    position_title: Optional[str] = None
    interviewers: Optional[List[Dict[str, Any]]] = None
    feedback_summary: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# =============================================================================
# Candidate Self-Scheduling Schemas
# =============================================================================

class SelfSchedulingLinkCreate(BaseModel):
    """Create a self-scheduling link for candidate."""
    interview_request_id: UUID
    available_slots: List[TimeSlot] = Field(..., min_length=1)
    expires_at: Optional[datetime] = None
    max_reschedules: int = Field(default=2, ge=0, le=5)
    custom_message: Optional[str] = None


class SelfSchedulingLinkResponse(BaseModel):
    """Response with self-scheduling link details."""
    id: UUID
    interview_request_id: UUID
    token: str
    link_url: str
    available_slots: List[TimeSlot]
    expires_at: Optional[datetime] = None
    max_reschedules: int
    reschedule_count: int = 0
    is_used: bool = False
    selected_slot: Optional[TimeSlot] = None
    created_at: datetime

    # Joined data
    candidate_name: Optional[str] = None
    position_title: Optional[str] = None
    interview_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    interviewers: Optional[List[str]] = None

    class Config:
        from_attributes = True


class CandidateSlotSelection(BaseModel):
    """Candidate selecting a time slot from self-scheduling link."""
    slot_index: int = Field(..., ge=0, description="Index of selected slot")
    candidate_timezone: str = Field(default="America/New_York")
    candidate_notes: Optional[str] = None


class CandidateRescheduleRequest(BaseModel):
    """Candidate requesting to reschedule."""
    reason: str = Field(..., min_length=1, max_length=500)
    preferred_dates: Optional[List[date]] = None


# =============================================================================
# Calendar Integration Schemas
# =============================================================================

class CalendarEventCreate(BaseModel):
    """Create a calendar event."""
    interview_schedule_id: UUID
    provider: CalendarProvider
    attendee_emails: List[EmailStr]
    include_candidate: bool = True
    include_video_link: bool = True


class CalendarEventResponse(BaseModel):
    """Response with calendar event details."""
    id: UUID
    interview_schedule_id: UUID
    provider: CalendarProvider
    event_id: str  # Provider's event ID
    event_link: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CalendarSyncStatus(BaseModel):
    """Status of calendar sync for a user."""
    user_id: UUID
    provider: CalendarProvider
    is_connected: bool
    last_synced_at: Optional[datetime] = None
    sync_errors: Optional[List[str]] = None


# =============================================================================
# Interview Reminder Schemas
# =============================================================================

class InterviewReminderConfig(BaseModel):
    """Configuration for interview reminders."""
    send_to_candidate: bool = True
    send_to_interviewers: bool = True
    reminder_hours_before: List[int] = Field(
        default=[24, 1],
        description="Hours before interview to send reminders"
    )


class InterviewReminderResponse(BaseModel):
    """Response for a scheduled reminder."""
    id: UUID
    interview_schedule_id: UUID
    recipient_type: str  # "candidate" or "interviewer"
    recipient_email: str
    scheduled_for: datetime
    sent_at: Optional[datetime] = None
    status: str  # "pending", "sent", "failed"

    class Config:
        from_attributes = True


# =============================================================================
# Bulk Operations
# =============================================================================

class BulkAvailabilityRequest(BaseModel):
    """Request availability from multiple interviewers."""
    interview_request_id: UUID
    interviewer_ids: List[UUID]
    date_range_start: date
    date_range_end: date
    duration_minutes: int = 60
    expires_in_hours: int = Field(default=48, ge=1, le=168)
    custom_message: Optional[str] = None


class BulkScheduleCancel(BaseModel):
    """Cancel multiple scheduled interviews."""
    interview_schedule_ids: List[UUID]
    reason: str
    notify_candidates: bool = True
    notify_interviewers: bool = True


# =============================================================================
# Interview Analytics
# =============================================================================

class InterviewMetrics(BaseModel):
    """Interview scheduling metrics."""
    total_scheduled: int
    total_completed: int
    total_cancelled: int
    total_no_shows: int
    average_scheduling_time_hours: float
    average_feedback_submission_hours: float
    interviews_by_type: Dict[str, int]
    interviews_by_stage: Dict[str, int]


# =============================================================================
# Timezone Utilities
# =============================================================================

class TimezoneInfo(BaseModel):
    """Timezone information for display."""
    timezone_id: str
    display_name: str
    utc_offset: str
    current_time: datetime


class CommonTimezones(BaseModel):
    """List of common timezones."""
    timezones: List[TimezoneInfo]
