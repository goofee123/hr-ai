"""Bulk operations schemas for recruiting."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BulkStageChangeRequest(BaseModel):
    """Request for bulk stage change."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    target_stage: str = Field(..., min_length=1)
    notes: Optional[str] = None


class BulkStageChangeResponse(BaseModel):
    """Response for bulk stage change."""

    success_count: int
    failure_count: int
    failed_ids: list[UUID] = []
    errors: list[str] = []


class BulkRejectRequest(BaseModel):
    """Request for bulk rejection."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    rejection_reason_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    send_notification: bool = False


class BulkRejectResponse(BaseModel):
    """Response for bulk rejection."""

    rejected_count: int
    failure_count: int
    failed_ids: list[UUID] = []
    errors: list[str] = []


class BulkEmailRequest(BaseModel):
    """Request for bulk email sending."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    template_id: Optional[UUID] = None
    subject: str
    body: str


class BulkEmailResponse(BaseModel):
    """Response for bulk email."""

    sent_count: int
    failure_count: int
    failed_ids: list[UUID] = []


class BulkTagRequest(BaseModel):
    """Request for bulk tagging."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    tags: list[str] = Field(..., min_length=1)
    action: str = Field("add", pattern="^(add|remove)$")


class BulkTagResponse(BaseModel):
    """Response for bulk tagging."""

    updated_count: int
    failure_count: int
    failed_ids: list[UUID] = []


class BulkAssignRequest(BaseModel):
    """Request for bulk assignment."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    assignee_id: UUID
    notes: Optional[str] = None


class BulkAssignResponse(BaseModel):
    """Response for bulk assignment."""

    assigned_count: int
    failure_count: int
    failed_ids: list[UUID] = []


# Offer Management Schemas

class OfferCreate(BaseModel):
    """Request to create an offer."""

    application_id: UUID
    position_title: str
    department: Optional[str] = None
    base_salary: float = Field(..., gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    bonus_percent: Optional[float] = Field(None, ge=0, le=100)
    equity_shares: Optional[int] = Field(None, ge=0)
    start_date: str  # ISO date string
    expiration_date: Optional[str] = None  # ISO date string
    notes: Optional[str] = None
    offer_letter_template_id: Optional[UUID] = None


class OfferUpdate(BaseModel):
    """Request to update an offer."""

    position_title: Optional[str] = None
    department: Optional[str] = None
    base_salary: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    bonus_percent: Optional[float] = Field(None, ge=0, le=100)
    equity_shares: Optional[int] = Field(None, ge=0)
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None
    notes: Optional[str] = None


class OfferResponse(BaseModel):
    """Response with offer details."""

    id: UUID
    application_id: UUID
    candidate_id: UUID
    requisition_id: UUID
    position_title: str
    department: Optional[str] = None
    base_salary: float
    currency: str
    bonus_percent: Optional[float] = None
    equity_shares: Optional[int] = None
    total_compensation: float
    start_date: str
    expiration_date: Optional[str] = None
    status: str  # draft, pending_approval, approved, sent, accepted, declined, expired
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    created_by: UUID
    approved_by: Optional[UUID] = None
    approved_at: Optional[str] = None


class OfferApprovalRequest(BaseModel):
    """Request to approve or reject an offer."""

    action: str = Field(..., pattern="^(approve|reject)$")
    notes: Optional[str] = None


class OfferSendRequest(BaseModel):
    """Request to send an offer to candidate."""

    send_email: bool = True
    custom_message: Optional[str] = None


class OfferCandidateActionRequest(BaseModel):
    """Request for candidate action on offer."""

    action: str = Field(..., pattern="^(accept|decline|negotiate)$")
    negotiation_notes: Optional[str] = None
    counter_offer_salary: Optional[float] = None
