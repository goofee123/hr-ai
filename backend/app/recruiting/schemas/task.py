"""Task schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    """Base task schema."""

    task_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: str = "normal"


class TaskCreate(TaskBase):
    """Schema for creating a task."""

    application_id: Optional[UUID] = None
    requisition_id: Optional[UUID] = None
    candidate_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[str] = None
    assigned_to: Optional[UUID] = None
    status: Optional[str] = None


class TaskComplete(BaseModel):
    """Schema for completing a task."""

    notes: Optional[str] = None


class TaskResponse(TaskBase):
    """Schema for task response."""

    id: UUID
    tenant_id: UUID
    application_id: Optional[UUID]
    requisition_id: Optional[UUID]
    candidate_id: Optional[UUID]
    assigned_to: Optional[UUID]
    status: str
    completed_at: Optional[datetime]
    completed_by: Optional[UUID]
    reminder_sent: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskWithContext(TaskResponse):
    """Task with related context."""

    candidate_name: Optional[str] = None
    requisition_title: Optional[str] = None
    assigned_to_name: Optional[str] = None

    class Config:
        from_attributes = True
