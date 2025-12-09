"""Recruiter assignment schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RecruiterAssignmentCreate(BaseModel):
    """Schema for creating a recruiter assignment."""

    recruiter_id: UUID = Field(..., description="User ID of the recruiter to assign")
    sla_days: Optional[int] = Field(None, description="Override SLA days for this assignment")
    notes: Optional[str] = Field(None, description="Notes about the assignment")


class RecruiterReassign(BaseModel):
    """Schema for reassigning a job to a different recruiter."""

    new_recruiter_id: UUID = Field(..., description="User ID of the new recruiter")
    reassignment_reason: Optional[str] = Field(None, description="Reason for reassignment")
    notes: Optional[str] = Field(None, description="Additional notes")


class RecruiterAssignmentResponse(BaseModel):
    """Response schema for recruiter assignment."""

    id: UUID
    tenant_id: UUID
    requisition_id: UUID
    recruiter_id: UUID
    assigned_at: datetime
    assigned_by: Optional[UUID]
    sla_days: Optional[int]
    sla_deadline: Optional[datetime]
    status: str
    completed_at: Optional[datetime]
    reassigned_to: Optional[UUID]
    reassigned_at: Optional[datetime]
    reassignment_reason: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    # Enriched data (optionally populated)
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    job_title: Optional[str] = None
    requisition_number: Optional[str] = None

    class Config:
        from_attributes = True


class RecruiterAssignmentListResponse(BaseModel):
    """Simplified assignment for list views."""

    id: UUID
    requisition_id: UUID
    recruiter_id: UUID
    assigned_at: datetime
    sla_days: Optional[int]
    sla_deadline: Optional[datetime]
    status: str
    days_remaining: Optional[int] = None
    sla_status: Optional[str] = None  # 'green', 'amber', 'red'
    recruiter_name: Optional[str] = None
    job_title: Optional[str] = None
    requisition_number: Optional[str] = None

    class Config:
        from_attributes = True


class MyAssignmentsResponse(BaseModel):
    """Response for a recruiter's own assignments."""

    id: UUID
    requisition_id: UUID
    requisition_number: str
    job_title: str
    department_name: Optional[str] = None
    assigned_at: datetime
    sla_days: Optional[int]
    sla_deadline: Optional[datetime]
    status: str
    days_remaining: Optional[int] = None
    sla_status: Optional[str] = None  # 'green', 'amber', 'red'
    candidate_count: int = 0
    job_status: Optional[str] = None

    class Config:
        from_attributes = True


class SLAAlertResponse(BaseModel):
    """Response schema for SLA alerts."""

    id: UUID
    tenant_id: UUID
    alert_type: str  # 'amber', 'red'
    entity_type: str  # 'job_opening', 'recruiter_assignment'
    entity_id: UUID
    message: Optional[str]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]

    # Enriched data
    entity_title: Optional[str] = None
    entity_number: Optional[str] = None
    recruiter_name: Optional[str] = None

    class Config:
        from_attributes = True


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an SLA alert."""

    notes: Optional[str] = Field(None, description="Optional notes about acknowledgment")
