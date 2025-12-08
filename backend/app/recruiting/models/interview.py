"""Interview models."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import TenantAwareBase


class InterviewSchedule(TenantAwareBase):
    """Interview schedule model."""

    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    application_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Interview Details
    interview_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    video_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Participants
    interviewer_ids: Mapped[Optional[List[UUID]]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), nullable=True)
    organizer_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)

    # Feedback
    feedback_due_by: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    all_feedback_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Calendar
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    feedback: Mapped[List["InterviewFeedback"]] = relationship(
        "InterviewFeedback", back_populates="interview"
    )


class InterviewFeedback(TenantAwareBase):
    """Interview feedback model."""

    __tablename__ = "interview_feedback"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    interviewer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Ratings
    overall_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ratings_by_competency: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Feedback
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    concerns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    interview: Mapped["InterviewSchedule"] = relationship(
        "InterviewSchedule", back_populates="feedback"
    )
