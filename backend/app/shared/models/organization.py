"""Organization structure models."""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import TenantAwareBase


class Department(TenantAwareBase):
    """Department model."""

    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id"),
        nullable=True,
    )
    manager_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    cost_center: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    parent: Mapped[Optional["Department"]] = relationship(
        "Department", remote_side="Department.id", backref="children"
    )


class Location(TenantAwareBase):
    """Location model."""

    __tablename__ = "locations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PayGrade(TenantAwareBase):
    """Pay grade/band model."""

    __tablename__ = "pay_grades"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    min_hourly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    mid_hourly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    max_hourly: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    min_annual: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    mid_annual: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    max_annual: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class InternalJobTitle(TenantAwareBase):
    """Internal job title model."""

    __tablename__ = "internal_job_titles"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_family: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_pay_grade_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pay_grades.id"),
        nullable=True,
    )
    flsa_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    default_pay_grade: Mapped[Optional["PayGrade"]] = relationship("PayGrade")
