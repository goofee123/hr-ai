"""Base model classes with common functionality."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )


class TenantAwareBase(Base, TimestampMixin):
    """Base class for all tenant-scoped models."""

    __abstract__ = True

    @declared_attr
    def tenant_id(cls) -> Mapped[UUID]:
        return mapped_column(
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class AuditMixin:
    """Mixin for models that track who created/updated them."""

    @declared_attr
    def created_by(cls) -> Mapped[Optional[UUID]]:
        return mapped_column(
            ForeignKey("users.id"),
            nullable=True,
        )

    @declared_attr
    def updated_by(cls) -> Mapped[Optional[UUID]]:
        return mapped_column(
            ForeignKey("users.id"),
            nullable=True,
        )
