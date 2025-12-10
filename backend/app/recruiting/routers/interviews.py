"""Interview scheduling router - using Supabase REST API."""

from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.interview import (
    InterviewRequestCreate,
    InterviewRequestUpdate,
    InterviewRequestResponse,
    InterviewScheduleCreate,
    InterviewScheduleUpdate,
    InterviewScheduleResponse,
    InterviewerAvailabilitySubmit,
    InterviewerAvailabilityResponse,
    SelfSchedulingLinkCreate,
    SelfSchedulingLinkResponse,
    CandidateSlotSelection,
    InterviewMetrics,
    BulkAvailabilityRequest,
    TimeSlot,
)
from app.recruiting.services.interview_scheduling import get_interview_scheduling_service

router = APIRouter()


# =============================================================================
# Interview Request Endpoints
# =============================================================================


@router.post("/requests", response_model=InterviewRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_interview_request(
    request_data: InterviewRequestCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """
    Create a new interview scheduling request.

    This initiates the interview scheduling workflow by creating a request
    that can then have availability collected from interviewers.
    """
    service = get_interview_scheduling_service()

    result = await service.create_interview_request(
        tenant_id=current_user.tenant_id,
        application_id=request_data.application_id,
        stage_name=request_data.stage_name,
        interview_type=request_data.interview_type.value,
        title=request_data.title,
        interviewer_ids=request_data.interviewer_ids,
        created_by=current_user.user_id,
        duration_minutes=request_data.duration_minutes,
        description=request_data.description,
        preferred_date_range_start=request_data.preferred_date_range_start,
        preferred_date_range_end=request_data.preferred_date_range_end,
        location=request_data.location,
        video_link=request_data.video_link,
        notes=request_data.notes,
    )

    return InterviewRequestResponse.model_validate(result)


@router.get("/requests", response_model=List[InterviewRequestResponse])
async def list_interview_requests(
    application_id: Optional[UUID] = Query(None, description="Filter by application"),
    request_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """List interview requests with optional filters."""
    service = get_interview_scheduling_service()

    requests, total = await service.list_interview_requests(
        tenant_id=current_user.tenant_id,
        application_id=application_id,
        status=request_status,
        page=page,
        page_size=page_size,
    )

    return [InterviewRequestResponse.model_validate(r) for r in requests]


@router.get("/requests/{request_id}", response_model=InterviewRequestResponse)
async def get_interview_request(
    request_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get a specific interview request with all related data."""
    service = get_interview_scheduling_service()

    result = await service.get_interview_request(
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview request not found",
        )

    return InterviewRequestResponse.model_validate(result)


# =============================================================================
# Availability Collection Endpoints
# =============================================================================


@router.post("/requests/{request_id}/request-availability")
async def request_availability_from_interviewers(
    request_id: UUID,
    request_data: BulkAvailabilityRequest,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """
    Request availability from interviewers for an interview request.

    Sends availability request emails to all specified interviewers.
    """
    service = get_interview_scheduling_service()

    results = []
    for interviewer_id in request_data.interviewer_ids:
        result = await service.request_interviewer_availability(
            tenant_id=current_user.tenant_id,
            interview_request_id=request_id,
            interviewer_id=interviewer_id,
            date_range_start=request_data.date_range_start,
            date_range_end=request_data.date_range_end,
            duration_minutes=request_data.duration_minutes,
            expires_in_hours=request_data.expires_in_hours,
            send_email=True,
        )
        results.append(result)

    return {
        "message": f"Availability requested from {len(results)} interviewers",
        "availability_requests": results,
    }


@router.get("/availability/{availability_id}", response_model=InterviewerAvailabilityResponse)
async def get_interviewer_availability(
    availability_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get an interviewer availability request."""
    from app.core.supabase_client import get_supabase_client
    import json

    client = get_supabase_client()

    availability = await client.select(
        "interviewer_availability",
        "*",
        filters={
            "id": str(availability_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability request not found",
        )

    # Parse JSON fields
    if isinstance(availability.get("available_slots"), str):
        availability["available_slots"] = json.loads(availability["available_slots"])

    return InterviewerAvailabilityResponse.model_validate(availability)


@router.post("/availability/{availability_id}/submit", response_model=InterviewerAvailabilityResponse)
async def submit_interviewer_availability(
    availability_id: UUID,
    availability_data: InterviewerAvailabilitySubmit,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """
    Submit availability for an interviewer.

    Interviewers use this endpoint to submit their available time slots.
    """
    service = get_interview_scheduling_service()

    # Convert TimeSlot objects to dicts
    slots = [
        {
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "timezone": slot.timezone,
        }
        for slot in availability_data.available_slots
    ]

    patterns = None
    if availability_data.weekly_patterns:
        patterns = [p.model_dump() for p in availability_data.weekly_patterns]

    result = await service.submit_interviewer_availability(
        tenant_id=current_user.tenant_id,
        availability_id=availability_id,
        interviewer_id=current_user.user_id,
        available_slots=slots,
        weekly_patterns=patterns,
        notes=availability_data.notes,
    )

    return InterviewerAvailabilityResponse.model_validate(result)


# =============================================================================
# Interview Scheduling Endpoints
# =============================================================================


@router.post("/schedule", response_model=InterviewScheduleResponse, status_code=status.HTTP_201_CREATED)
async def schedule_interview(
    schedule_data: InterviewScheduleCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """
    Schedule an interview at a specific time.

    Creates calendar events and sends notifications to all participants.
    """
    service = get_interview_scheduling_service()

    result = await service.schedule_interview(
        tenant_id=current_user.tenant_id,
        interview_request_id=schedule_data.interview_request_id,
        scheduled_at=schedule_data.scheduled_at,
        organizer_id=current_user.user_id,
        timezone=schedule_data.timezone,
        location=schedule_data.location,
        video_link=schedule_data.video_link,
        send_calendar_invites=schedule_data.send_calendar_invites,
        send_candidate_email=schedule_data.send_candidate_email,
        custom_message=schedule_data.custom_message,
    )

    return InterviewScheduleResponse.model_validate(result)


@router.get("/schedules", response_model=List[InterviewScheduleResponse])
async def list_interview_schedules(
    application_id: Optional[UUID] = Query(None, description="Filter by application"),
    schedule_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Start of date range"),
    end_date: Optional[date] = Query(None, description="End of date range"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """List scheduled interviews with optional filters."""
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    filters = {"tenant_id": str(current_user.tenant_id)}

    if application_id:
        filters["application_id"] = str(application_id)
    if schedule_status:
        filters["status"] = schedule_status

    schedules = await client.select(
        "interview_schedules",
        "*",
        filters=filters,
        return_empty_on_404=True,
    ) or []

    # Filter by date range
    if start_date:
        schedules = [
            s for s in schedules
            if s.get("scheduled_at", "")[:10] >= start_date.isoformat()
        ]
    if end_date:
        schedules = [
            s for s in schedules
            if s.get("scheduled_at", "")[:10] <= end_date.isoformat()
        ]

    # Sort by scheduled_at desc
    schedules.sort(key=lambda x: x.get("scheduled_at", ""), reverse=True)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    schedules = schedules[start:end]

    return [InterviewScheduleResponse.model_validate(s) for s in schedules]


@router.get("/schedules/{schedule_id}", response_model=InterviewScheduleResponse)
async def get_interview_schedule(
    schedule_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get a specific scheduled interview."""
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    schedule = await client.select(
        "interview_schedules",
        "*",
        filters={
            "id": str(schedule_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview schedule not found",
        )

    return InterviewScheduleResponse.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=InterviewScheduleResponse)
async def update_interview_schedule(
    schedule_id: UUID,
    update_data: InterviewScheduleUpdate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Update a scheduled interview."""
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    # Verify exists
    existing = await client.select(
        "interview_schedules",
        "id",
        filters={
            "id": str(schedule_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview schedule not found",
        )

    # Build update
    update_dict = update_data.model_dump(exclude_unset=True)
    if "scheduled_at" in update_dict and update_dict["scheduled_at"]:
        update_dict["scheduled_at"] = update_dict["scheduled_at"].isoformat()
    if "status" in update_dict and update_dict["status"]:
        update_dict["status"] = update_dict["status"].value

    schedule = await client.update(
        "interview_schedules",
        update_dict,
        filters={"id": str(schedule_id)},
    )

    return InterviewScheduleResponse.model_validate(schedule)


@router.post("/schedules/{schedule_id}/reschedule", response_model=InterviewScheduleResponse)
async def reschedule_interview(
    schedule_id: UUID,
    new_time: datetime,
    reason: Optional[str] = None,
    notify_participants: bool = True,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Reschedule an interview to a new time."""
    service = get_interview_scheduling_service()

    result = await service.reschedule_interview(
        tenant_id=current_user.tenant_id,
        schedule_id=schedule_id,
        new_scheduled_at=new_time,
        reason=reason,
        notify_participants=notify_participants,
    )

    return InterviewScheduleResponse.model_validate(result)


@router.post("/schedules/{schedule_id}/cancel")
async def cancel_interview(
    schedule_id: UUID,
    reason: str,
    notify_participants: bool = True,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Cancel a scheduled interview."""
    service = get_interview_scheduling_service()

    result = await service.cancel_interview(
        tenant_id=current_user.tenant_id,
        schedule_id=schedule_id,
        reason=reason,
        notify_participants=notify_participants,
    )

    return {"message": "Interview cancelled", "schedule": result}


@router.post("/schedules/{schedule_id}/complete")
async def mark_interview_complete(
    schedule_id: UUID,
    notes: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Mark an interview as completed."""
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    update_data = {
        "status": "completed",
    }
    if notes:
        update_data["notes"] = notes

    schedule = await client.update(
        "interview_schedules",
        update_data,
        filters={
            "id": str(schedule_id),
            "tenant_id": str(current_user.tenant_id),
        },
    )

    return {"message": "Interview marked as completed", "schedule": schedule}


@router.post("/schedules/{schedule_id}/no-show")
async def mark_interview_no_show(
    schedule_id: UUID,
    who_no_showed: str,  # "candidate" or "interviewer"
    notes: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """Mark an interview as no-show."""
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    update_data = {
        "status": "no_show",
        "notes": f"No-show by {who_no_showed}. {notes or ''}".strip(),
    }

    schedule = await client.update(
        "interview_schedules",
        update_data,
        filters={
            "id": str(schedule_id),
            "tenant_id": str(current_user.tenant_id),
        },
    )

    return {"message": f"Interview marked as no-show by {who_no_showed}", "schedule": schedule}


# =============================================================================
# Self-Scheduling Endpoints
# =============================================================================


@router.post("/self-scheduling/create", response_model=SelfSchedulingLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_self_scheduling_link(
    link_data: SelfSchedulingLinkCreate,
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_WRITE)),
):
    """
    Create a self-scheduling link for a candidate.

    The link allows the candidate to pick a time slot without logging in.
    """
    service = get_interview_scheduling_service()

    # Convert TimeSlot objects to dicts
    slots = [
        {
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "timezone": slot.timezone,
        }
        for slot in link_data.available_slots
    ]

    result = await service.create_self_scheduling_link(
        tenant_id=current_user.tenant_id,
        interview_request_id=link_data.interview_request_id,
        available_slots=slots,
        created_by=current_user.user_id,
        expires_in_hours=72 if not link_data.expires_at else int(
            (link_data.expires_at - datetime.utcnow()).total_seconds() / 3600
        ),
        max_reschedules=link_data.max_reschedules,
        custom_message=link_data.custom_message,
    )

    return SelfSchedulingLinkResponse.model_validate(result)


@router.get("/self-scheduling/{token}", response_model=SelfSchedulingLinkResponse)
async def get_self_scheduling_link_public(
    token: str,
):
    """
    Get self-scheduling link details (public endpoint).

    This endpoint doesn't require authentication - it's accessed by candidates.
    """
    service = get_interview_scheduling_service()

    result = await service.get_self_scheduling_link(token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduling link not found",
        )

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return SelfSchedulingLinkResponse.model_validate(result)


@router.post("/self-scheduling/{token}/select", response_model=InterviewScheduleResponse)
async def select_slot_from_scheduling_link(
    token: str,
    selection: CandidateSlotSelection,
):
    """
    Candidate selects a time slot (public endpoint).

    This schedules the interview and returns the schedule details.
    """
    service = get_interview_scheduling_service()

    try:
        result = await service.select_slot_from_link(
            token=token,
            slot_index=selection.slot_index,
            candidate_timezone=selection.candidate_timezone,
            candidate_notes=selection.candidate_notes,
        )

        return InterviewScheduleResponse.model_validate(result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# My Interviews (For Interviewers)
# =============================================================================


@router.get("/my-interviews", response_model=List[InterviewScheduleResponse])
async def get_my_interviews(
    start_date: Optional[date] = Query(None, description="Start of date range"),
    end_date: Optional[date] = Query(None, description="End of date range"),
    include_past: bool = Query(False, description="Include past interviews"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """
    Get interviews where the current user is an interviewer.

    Returns upcoming interviews by default, unless include_past is True.
    """
    from app.core.supabase_client import get_supabase_client

    client = get_supabase_client()

    # Get all schedules for this tenant
    schedules = await client.select(
        "interview_schedules",
        "*",
        filters={"tenant_id": str(current_user.tenant_id)},
        return_empty_on_404=True,
    ) or []

    # Filter to only interviews where user is an interviewer
    user_id_str = str(current_user.user_id)
    my_interviews = [
        s for s in schedules
        if user_id_str in (s.get("interviewer_ids") or [])
    ]

    # Filter by date
    now = datetime.utcnow().isoformat()
    if not include_past:
        my_interviews = [
            s for s in my_interviews
            if s.get("scheduled_at", "") >= now or s.get("status") in ["scheduled", "confirmed"]
        ]

    if start_date:
        my_interviews = [
            s for s in my_interviews
            if s.get("scheduled_at", "")[:10] >= start_date.isoformat()
        ]
    if end_date:
        my_interviews = [
            s for s in my_interviews
            if s.get("scheduled_at", "")[:10] <= end_date.isoformat()
        ]

    # Sort by scheduled_at
    my_interviews.sort(key=lambda x: x.get("scheduled_at", ""))

    return [InterviewScheduleResponse.model_validate(s) for s in my_interviews]


@router.get("/my-availability-requests", response_model=List[InterviewerAvailabilityResponse])
async def get_my_availability_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """Get availability requests for the current interviewer."""
    from app.core.supabase_client import get_supabase_client
    import json

    client = get_supabase_client()

    filters = {
        "tenant_id": str(current_user.tenant_id),
        "interviewer_id": str(current_user.user_id),
    }

    if status_filter:
        filters["status"] = status_filter

    requests = await client.select(
        "interviewer_availability",
        "*",
        filters=filters,
        return_empty_on_404=True,
    ) or []

    # Parse JSON fields
    for req in requests:
        if isinstance(req.get("available_slots"), str):
            req["available_slots"] = json.loads(req["available_slots"])

    # Sort by created_at desc
    requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return [InterviewerAvailabilityResponse.model_validate(r) for r in requests]


# =============================================================================
# Metrics & Analytics
# =============================================================================


@router.get("/metrics", response_model=InterviewMetrics)
async def get_interview_metrics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_REPORTS)),
):
    """Get interview scheduling metrics."""
    service = get_interview_scheduling_service()

    metrics = await service.get_interview_metrics(
        tenant_id=current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )

    return InterviewMetrics(**metrics)


# =============================================================================
# Available Time Slots (Find Common Availability)
# =============================================================================


@router.get("/available-slots")
async def find_available_slots(
    interviewer_ids: str = Query(..., description="Comma-separated interviewer IDs"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    duration_minutes: int = Query(60),
    timezone: str = Query("America/New_York"),
    current_user: TokenData = Depends(require_permission(Permission.RECRUITING_READ)),
):
    """
    Find available time slots for a group of interviewers.

    Uses calendar integration (if available) to find common availability.
    """
    from app.recruiting.services.calendar_service import get_calendar_service

    calendar_service = get_calendar_service()

    # Parse interviewer IDs
    interviewer_id_list = [UUID(id.strip()) for id in interviewer_ids.split(",")]

    # Find available slots
    slots = await calendar_service.find_available_slots(
        interviewer_emails=[],  # Would need to look up emails
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time()),
        duration_minutes=duration_minutes,
        timezone=timezone,
    )

    return {
        "available_slots": slots[:50],  # Limit to 50 slots
        "total_slots_found": len(slots),
        "timezone": timezone,
    }
