"""Schemas for merge queue / duplicate candidate review."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# MATCH REASON TYPES
# =============================================================================

class DuplicateMatchReason(BaseModel):
    """Individual reason for duplicate match with confidence."""
    type: str = Field(
        ...,
        description="Reason type: email_match, linkedin_match, name_similarity, resume_similarity, company_overlap, phone_match"
    )
    confidence: float = Field(..., ge=0, le=1)
    detail: Optional[str] = Field(None, description="Additional detail (e.g., 'Worked at TechCorp 2020-2023')")


# =============================================================================
# CANDIDATE SUMMARY
# =============================================================================

class CandidateSummary(BaseModel):
    """Brief summary of a candidate for merge queue display."""
    id: UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    created_at: datetime
    application_count: int = 0


# =============================================================================
# MERGE QUEUE ITEM
# =============================================================================

class MergeQueueItemBase(BaseModel):
    """Base schema for merge queue item."""
    primary_candidate_id: UUID
    duplicate_candidate_id: UUID
    match_score: float = Field(..., ge=0, le=1)
    match_type: str = Field(
        ...,
        description="hard (auto-merge), strong (95%+), fuzzy (80-95%), review (60-80%)"
    )
    reasons: list[DuplicateMatchReason]


class MergeQueueItemCreate(MergeQueueItemBase):
    """Schema for creating a merge queue item."""
    pass


class MergeQueueItemResponse(MergeQueueItemBase):
    """Schema for merge queue item response."""
    id: UUID
    tenant_id: UUID
    status: str = Field(
        default="pending",
        description="pending, merged, rejected, deferred"
    )
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    review_notes: Optional[str] = None

    model_config = {"from_attributes": True}


class MergeQueueItemDetail(MergeQueueItemResponse):
    """Detailed merge queue item with candidate summaries."""
    primary_candidate: CandidateSummary
    duplicate_candidate: CandidateSummary


# =============================================================================
# LIST RESPONSE
# =============================================================================

class MergeQueueListResponse(BaseModel):
    """Paginated list of merge queue items."""
    items: list[MergeQueueItemDetail]
    total: int
    page: int
    page_size: int
    total_pages: int
    stats: dict[str, int] = Field(
        default_factory=dict,
        description="Counts by status: {pending: 5, merged: 10, rejected: 2}"
    )


# =============================================================================
# MERGE / REJECT REQUESTS
# =============================================================================

class MergeCandidatesRequest(BaseModel):
    """Request to merge two candidates."""
    primary_candidate_id: UUID = Field(..., description="The candidate to keep")
    duplicate_candidate_id: UUID = Field(..., description="The candidate to merge into primary")
    merge_queue_item_id: Optional[UUID] = Field(
        None,
        description="If merging from queue, the queue item ID"
    )
    merge_strategy: str = Field(
        default="smart_merge",
        description="prefer_new, prefer_existing, smart_merge"
    )
    notes: Optional[str] = Field(None, description="Reviewer notes about the merge")


class RejectDuplicateRequest(BaseModel):
    """Request to reject a duplicate (mark as not same person)."""
    merge_queue_item_id: UUID
    reason: Optional[str] = Field(None, description="Why this was rejected as duplicate")


class DeferDuplicateRequest(BaseModel):
    """Request to defer a duplicate decision for later."""
    merge_queue_item_id: UUID
    notes: Optional[str] = Field(None, description="Notes for future review")


# =============================================================================
# MERGE RESPONSE
# =============================================================================

class MergeResultResponse(BaseModel):
    """Response from merge operation."""
    success: bool
    primary_candidate_id: UUID
    merged_candidate_id: UUID
    merge_strategy: str
    changes_applied: dict[str, Any] = Field(
        default_factory=dict,
        description="What changed during merge"
    )
    new_resume_id: Optional[UUID] = None
    resume_version: Optional[int] = None


# =============================================================================
# DUPLICATE DETECTION REQUEST
# =============================================================================

class DetectDuplicatesRequest(BaseModel):
    """Request to find duplicates for a candidate."""
    candidate_id: UUID
    min_confidence: float = Field(default=0.6, ge=0, le=1)


class DetectDuplicatesResponse(BaseModel):
    """Response with potential duplicates."""
    candidate_id: UUID
    duplicates: list[MergeQueueItemDetail]
    auto_merge_count: int = Field(0, description="Number of hard matches found")
    review_count: int = Field(0, description="Number needing human review")
