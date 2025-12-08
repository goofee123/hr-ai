"""Job requisition models."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import TenantAwareBase


class RequisitionTemplate(TenantAwareBase):
    """Pipeline template for requisitions."""

    __tablename__ = "requisition_templates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_stages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    default_sla_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class JobRequisition(TenantAwareBase):
    """Job requisition model."""

    __tablename__ = "job_requisitions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    requisition_number: Mapped[str] = mapped_column(String(50), nullable=False)

    # Job Details
    internal_title_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("internal_job_titles.id"),
        nullable=True,
    )
    internal_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Organization
    department_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id"),
        nullable=True,
    )
    location_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=True,
    )
    reports_to_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Compensation
    pay_grade_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pay_grades.id"),
        nullable=True,
    )
    salary_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    target_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_salary_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Headcount
    positions_approved: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    positions_filled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_type: Mapped[str] = mapped_column(String(50), default="full_time", nullable=False)

    # Workflow
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("requisition_templates.id"),
        nullable=True,
    )
    pipeline_stages: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Assignment
    primary_recruiter_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    hiring_manager_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # SLA Tracking
    target_fill_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sla_days: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Approvals
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Posting
    is_posted_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_posted_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    posting_urls: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Relationships
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="requisition"
    )
    stages: Mapped[List["PipelineStage"]] = relationship(
        "PipelineStage", back_populates="requisition"
    )


class PipelineStage(TenantAwareBase):
    """Pipeline stage for a requisition."""

    __tablename__ = "pipeline_stages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    requisition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("job_requisitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_rejection_stage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_advance_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requires_feedback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interview_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    requisition: Mapped["JobRequisition"] = relationship(
        "JobRequisition", back_populates="stages"
    )


# Import Application here to avoid circular imports
from app.recruiting.models.candidate import Application
