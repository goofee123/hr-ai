"""Candidate and application models."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import TenantAwareBase


class Candidate(TenantAwareBase):
    """Candidate model."""

    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )

    # Contact Info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Source
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_detail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referred_by_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Classification
    worker_type_preference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_internal_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_employee_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Tags/Skills
    skills: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    # Privacy
    is_do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gdpr_consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gdpr_expiry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Aggregates
    total_applications: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="candidate")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="candidate")

    @property
    def full_name(self) -> str:
        """Get candidate's full name."""
        return f"{self.first_name} {self.last_name}"


class Resume(TenantAwareBase):
    """Resume model."""

    __tablename__ = "resumes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # File Storage
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Parsed Data
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Versioning
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Parsing Status
    parsing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="resumes")


class Application(TenantAwareBase):
    """Application model - links candidate to requisition."""

    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    requisition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("job_requisitions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    current_stage: Mapped[str] = mapped_column(String(100), default="Applied", nullable=False)
    current_stage_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=True,
    )
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Resume
    resume_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resumes.id"),
        nullable=True,
    )
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Screening
    screening_answers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Scores
    recruiter_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hiring_manager_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Rejection
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rejection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Offer
    offer_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Assignment
    assigned_recruiter_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Timing
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="applications")
    requisition: Mapped["JobRequisition"] = relationship("JobRequisition", back_populates="applications")
    events: Mapped[List["ApplicationEvent"]] = relationship("ApplicationEvent", back_populates="application")


class ApplicationEvent(TenantAwareBase):
    """Application event for audit trail."""

    __tablename__ = "application_events"

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

    # Event Details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Actor
    performed_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Visibility
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="events")


# Import at end to avoid circular imports
from app.recruiting.models.job import JobRequisition
