"""Router for candidate merge queue / duplicate review."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.merge_queue import (
    CandidateSummary,
    DeferDuplicateRequest,
    DetectDuplicatesRequest,
    DetectDuplicatesResponse,
    DuplicateMatchReason,
    MergeCandidatesRequest,
    MergeQueueItemDetail,
    MergeQueueListResponse,
    MergeResultResponse,
    RejectDuplicateRequest,
)
from app.recruiting.services.merge_queue_service import get_merge_queue_service

router = APIRouter()


# =============================================================================
# LIST & GET
# =============================================================================

@router.get("", response_model=MergeQueueListResponse)
async def list_merge_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status: pending, merged, rejected, deferred"
    ),
    match_type_filter: Optional[str] = Query(
        None,
        description="Filter by match type: hard, strong, fuzzy, review"
    ),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get paginated list of duplicate candidate pairs for review.

    Returns items with candidate summaries and match reasons.
    """
    service = get_merge_queue_service()
    return await service.list_queue_items(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        match_type_filter=match_type_filter,
    )


@router.get("/{item_id}", response_model=MergeQueueItemDetail)
async def get_merge_queue_item(
    item_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get a single merge queue item with full candidate details."""
    service = get_merge_queue_service()
    item = await service.get_queue_item(current_user.tenant_id, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merge queue item not found",
        )

    return item


# =============================================================================
# DETECT DUPLICATES
# =============================================================================

@router.post("/detect", response_model=DetectDuplicatesResponse)
async def detect_duplicates(
    request: DetectDuplicatesRequest,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Find potential duplicates for a candidate.

    This does not add items to the queue - use for preview before creating items.
    """
    service = get_merge_queue_service()
    return await service.detect_duplicates(
        tenant_id=current_user.tenant_id,
        candidate_id=request.candidate_id,
        min_confidence=request.min_confidence,
    )


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def scan_for_duplicates(
    limit: int = Query(100, ge=1, le=1000, description="Max candidates to scan"),
    add_to_queue: bool = Query(True, description="Add found duplicates to queue"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Scan tenant's candidates for duplicates and optionally add to queue.

    This is a background operation for data cleanup.
    Returns immediately with job status.
    """
    service = get_merge_queue_service()
    result = await service.scan_all_candidates(
        tenant_id=current_user.tenant_id,
        limit=limit,
        add_to_queue=add_to_queue,
        triggered_by=current_user.user_id,
    )

    return {
        "status": "completed",
        "candidates_scanned": result.get("candidates_scanned", 0),
        "duplicates_found": result.get("duplicates_found", 0),
        "items_added_to_queue": result.get("items_added", 0),
    }


# =============================================================================
# MERGE OPERATIONS
# =============================================================================

@router.post("/merge", response_model=MergeResultResponse)
async def merge_candidates(
    request: MergeCandidatesRequest,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Merge two candidates.

    The duplicate_candidate's data, resumes, and applications are merged
    into the primary_candidate. The duplicate is then soft-deleted.

    Strategies:
    - prefer_new: Use new data where provided
    - prefer_existing: Only fill in blanks
    - smart_merge: Heuristics (newer data wins, aggregate skills, etc.)
    """
    service = get_merge_queue_service()

    try:
        result = await service.merge_candidates(
            tenant_id=current_user.tenant_id,
            primary_candidate_id=request.primary_candidate_id,
            duplicate_candidate_id=request.duplicate_candidate_id,
            merge_queue_item_id=request.merge_queue_item_id,
            merge_strategy=request.merge_strategy,
            merged_by=current_user.user_id,
            notes=request.notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/reject", status_code=status.HTTP_200_OK)
async def reject_duplicate(
    request: RejectDuplicateRequest,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Reject a merge queue item (mark as not actually duplicates)."""
    service = get_merge_queue_service()

    success = await service.reject_duplicate(
        tenant_id=current_user.tenant_id,
        merge_queue_item_id=request.merge_queue_item_id,
        rejected_by=current_user.user_id,
        reason=request.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merge queue item not found",
        )

    return {"status": "rejected", "merge_queue_item_id": str(request.merge_queue_item_id)}


@router.post("/defer", status_code=status.HTTP_200_OK)
async def defer_duplicate(
    request: DeferDuplicateRequest,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Defer a merge decision for later review."""
    service = get_merge_queue_service()

    success = await service.defer_duplicate(
        tenant_id=current_user.tenant_id,
        merge_queue_item_id=request.merge_queue_item_id,
        deferred_by=current_user.user_id,
        notes=request.notes,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merge queue item not found",
        )

    return {"status": "deferred", "merge_queue_item_id": str(request.merge_queue_item_id)}


# =============================================================================
# STATS
# =============================================================================

@router.get("/stats/summary")
async def get_queue_stats(
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get summary statistics for the merge queue."""
    service = get_merge_queue_service()
    return await service.get_queue_stats(current_user.tenant_id)
