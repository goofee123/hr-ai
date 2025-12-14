"""Router for candidate observations, emails, and activity events."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.observation import (
    ActivityEventCreate,
    ActivityEventResponse,
    CandidateActivityFeed,
    CandidateEmailCreate,
    CandidateEmailResponse,
    CandidateEmailsResponse,
    CandidateEmailUpdate,
    CandidateObservationsResponse,
    ObservationBulkCreate,
    ObservationCreate,
    ObservationResponse,
)
from app.recruiting.services.observation_service import get_observation_service
from app.recruiting.services.activity_tracker import get_activity_tracker

router = APIRouter()


# =============================================================================
# CANDIDATE EMAILS
# =============================================================================

@router.get("/candidates/{candidate_id}/emails", response_model=CandidateEmailsResponse)
async def get_candidate_emails(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get all emails for a candidate."""
    service = get_observation_service()
    emails = await service.get_candidate_emails(current_user.tenant_id, candidate_id)

    primary_email = None
    for email in emails:
        if email.is_primary:
            primary_email = email.email
            break

    return CandidateEmailsResponse(
        candidate_id=candidate_id,
        emails=emails,
        primary_email=primary_email,
    )


@router.post(
    "/candidates/{candidate_id}/emails",
    response_model=CandidateEmailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_candidate_email(
    candidate_id: UUID,
    email_data: CandidateEmailCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Add an email to a candidate."""
    service = get_observation_service()

    try:
        result = await service.add_candidate_email(
            current_user.tenant_id, candidate_id, email_data
        )
        return result
    except Exception as e:
        # Check for unique constraint violation
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists for another candidate in this tenant",
            )
        raise


@router.patch("/emails/{email_id}", response_model=CandidateEmailResponse)
async def update_candidate_email(
    email_id: UUID,
    email_data: CandidateEmailUpdate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Update a candidate email."""
    service = get_observation_service()
    result = await service.update_candidate_email(
        current_user.tenant_id, email_id, email_data
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    return result


@router.delete("/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_email(
    email_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Delete a candidate email."""
    service = get_observation_service()
    success = await service.delete_candidate_email(current_user.tenant_id, email_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    return None


@router.get("/emails/lookup")
async def find_candidate_by_email(
    email: str = Query(..., description="Email address to look up"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Find a candidate by email address."""
    service = get_observation_service()
    candidate_id = await service.find_candidate_by_email(
        current_user.tenant_id, email
    )

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidate found with this email",
        )

    return {"candidate_id": candidate_id}


# =============================================================================
# CANDIDATE OBSERVATIONS
# =============================================================================

@router.get(
    "/candidates/{candidate_id}/observations",
    response_model=CandidateObservationsResponse,
)
async def get_candidate_observations(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get all current observations for a candidate, grouped by field."""
    service = get_observation_service()
    return await service.get_observations_summary(current_user.tenant_id, candidate_id)


@router.get(
    "/candidates/{candidate_id}/observations/all",
    response_model=list[ObservationResponse],
)
async def get_candidate_observations_all(
    candidate_id: UUID,
    current_only: bool = Query(True, description="Only return current observations"),
    field_name: Optional[str] = Query(None, description="Filter by field name"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get all observations for a candidate (including superseded if requested)."""
    service = get_observation_service()
    return await service.get_candidate_observations(
        current_user.tenant_id, candidate_id, current_only, field_name
    )


@router.post(
    "/candidates/{candidate_id}/observations",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_observation(
    candidate_id: UUID,
    observation_data: ObservationCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Add an observation for a candidate."""
    service = get_observation_service()
    return await service.add_observation(
        current_user.tenant_id,
        candidate_id,
        observation_data,
        extracted_by=current_user.user_id,
    )


@router.post(
    "/candidates/{candidate_id}/observations/bulk",
    response_model=list[ObservationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_observations_bulk(
    candidate_id: UUID,
    bulk_data: ObservationBulkCreate,
    supersede_existing: bool = Query(
        True, description="Supersede existing observations"
    ),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Add multiple observations for a candidate (e.g., from LLM extraction)."""
    service = get_observation_service()
    return await service.add_observations_bulk(
        current_user.tenant_id,
        candidate_id,
        bulk_data.observations,
        extracted_by=current_user.user_id,
        supersede_existing=supersede_existing,
    )


@router.post(
    "/observations/{observation_id}/supersede",
    response_model=ObservationResponse,
)
async def supersede_observation(
    observation_id: UUID,
    new_observation: ObservationCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Supersede an observation with a new value."""
    service = get_observation_service()
    result = await service.supersede_observation(
        current_user.tenant_id,
        observation_id,
        new_observation,
        extracted_by=current_user.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )

    return result


@router.delete("/observations/{observation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observation(
    observation_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Delete an observation."""
    service = get_observation_service()
    success = await service.delete_observation(current_user.tenant_id, observation_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )

    return None


# =============================================================================
# CANDIDATE ACTIVITY
# =============================================================================

@router.get("/candidates/{candidate_id}/activity", response_model=CandidateActivityFeed)
async def get_candidate_activity(
    candidate_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    event_types: Optional[str] = Query(
        None, description="Comma-separated event types to filter"
    ),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get activity feed for a candidate."""
    tracker = get_activity_tracker()

    event_type_list = None
    if event_types:
        event_type_list = [t.strip() for t in event_types.split(",")]

    return await tracker.get_candidate_activity(
        current_user.tenant_id,
        candidate_id,
        limit=limit,
        offset=offset,
        event_types=event_type_list,
    )


@router.post(
    "/candidates/{candidate_id}/activity",
    response_model=ActivityEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_activity_event(
    candidate_id: UUID,
    event: ActivityEventCreate,
    request: Request,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_EDIT)),
):
    """Log an activity event for a candidate."""
    tracker = get_activity_tracker()

    # Get client info from request
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await tracker.log_event_from_schema(
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
        event=event,
        user_id=current_user.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get("/activity/my-recent", response_model=list[ActivityEventResponse])
async def get_my_recent_activity(
    limit: int = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get recent activity for the current user (recruiter dashboard)."""
    tracker = get_activity_tracker()
    return await tracker.get_user_recent_activity(
        current_user.tenant_id, current_user.user_id, limit
    )


@router.get("/candidates/{candidate_id}/engagement")
async def get_candidate_engagement(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_VIEW)),
):
    """Get engagement metrics for a candidate."""
    tracker = get_activity_tracker()
    return await tracker.get_engagement_metrics(current_user.tenant_id, candidate_id)
