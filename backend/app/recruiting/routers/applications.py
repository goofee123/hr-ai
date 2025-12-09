"""Applications router using Supabase REST API."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.application import (
    ApplicationCreate,
    ApplicationEventResponse,
    ApplicationReject,
    ApplicationResponse,
    ApplicationStageUpdate,
    ApplicationUpdate,
    ApplicationWithCandidateResponse,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ApplicationWithCandidateResponse])
async def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    requisition_id: Optional[UUID] = None,
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    assigned_recruiter_id: Optional[UUID] = None,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List applications with filters."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}
    if requisition_id:
        filters["requisition_id"] = str(requisition_id)
    if candidate_id:
        filters["candidate_id"] = str(candidate_id)
    if status:
        filters["status"] = status
    if stage:
        filters["current_stage"] = stage
    if assigned_recruiter_id:
        filters["assigned_recruiter_id"] = str(assigned_recruiter_id)

    # Get applications with candidate info using PostgREST embedded resources
    offset = (page - 1) * page_size

    applications = await client.query(
        "applications",
        "*, candidates!applications_candidate_id_fkey(*)",
        filters=filters,
        order="applied_at",
        order_desc=True,
        limit=page_size,
        offset=offset,
    )

    # Get total count
    all_apps = await client.query(
        "applications",
        "id",
        filters=filters,
    )
    total = len(all_apps)

    # Build response
    items = []
    for app in applications:
        candidate = app.get("candidates") or {}
        items.append(
            ApplicationWithCandidateResponse(
                id=UUID(app["id"]),
                tenant_id=UUID(app["tenant_id"]),
                candidate_id=UUID(app["candidate_id"]),
                requisition_id=UUID(app["requisition_id"]),
                status=app.get("status", "active"),
                current_stage=app.get("current_stage", "Applied"),
                current_stage_id=UUID(app["current_stage_id"]) if app.get("current_stage_id") else None,
                stage_entered_at=datetime.fromisoformat(app["stage_entered_at"].replace("Z", "+00:00")) if app.get("stage_entered_at") else None,
                resume_id=UUID(app["resume_id"]) if app.get("resume_id") else None,
                cover_letter=app.get("cover_letter"),
                screening_answers=app.get("screening_answers") or {},
                recruiter_rating=app.get("recruiter_rating"),
                hiring_manager_rating=app.get("hiring_manager_rating"),
                overall_score=app.get("overall_score"),
                rejection_reason=app.get("rejection_reason"),
                rejection_notes=app.get("rejection_notes"),
                rejected_by=UUID(app["rejected_by"]) if app.get("rejected_by") else None,
                rejected_at=datetime.fromisoformat(app["rejected_at"].replace("Z", "+00:00")) if app.get("rejected_at") else None,
                offer_id=UUID(app["offer_id"]) if app.get("offer_id") else None,
                assigned_recruiter_id=UUID(app["assigned_recruiter_id"]) if app.get("assigned_recruiter_id") else None,
                applied_at=datetime.fromisoformat(app["applied_at"].replace("Z", "+00:00")) if app.get("applied_at") else None,
                last_activity_at=datetime.fromisoformat(app["last_activity_at"].replace("Z", "+00:00")) if app.get("last_activity_at") else None,
                created_at=datetime.fromisoformat(app["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(app["updated_at"].replace("Z", "+00:00")) if app.get("updated_at") else None,
                candidate_name=f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or "Unknown",
                candidate_email=candidate.get("email", ""),
                candidate_phone=candidate.get("phone"),
            )
        )

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: ApplicationCreate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_CREATE)),
):
    """Create a new application."""
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(application_data.candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Verify requisition exists and is open
    job = await client.select(
        "job_requisitions",
        "id,status,primary_recruiter_id",
        filters={
            "id": str(application_data.requisition_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    if job.get("status") not in ("open", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job requisition is not accepting applications",
        )

    # Check for existing application
    existing = await client.select(
        "applications",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "candidate_id": str(application_data.candidate_id),
            "requisition_id": str(application_data.requisition_id),
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate already applied for this position",
        )

    # Get initial stage
    stages = await client.query(
        "pipeline_stages",
        "id,name",
        filters={"requisition_id": str(application_data.requisition_id)},
        order="sort_order",
        limit=1,
    )
    initial_stage = stages[0] if stages else None

    now = datetime.now(timezone.utc)

    # Create application
    app_data = {
        "tenant_id": str(current_user.tenant_id),
        "candidate_id": str(application_data.candidate_id),
        "requisition_id": str(application_data.requisition_id),
        "resume_id": str(application_data.resume_id) if application_data.resume_id else None,
        "cover_letter": application_data.cover_letter,
        "screening_answers": application_data.screening_answers or {},
        "assigned_recruiter_id": str(application_data.assigned_recruiter_id) if application_data.assigned_recruiter_id else job.get("primary_recruiter_id"),
        "current_stage": initial_stage["name"] if initial_stage else "Applied",
        "current_stage_id": initial_stage["id"] if initial_stage else None,
        "stage_entered_at": now.isoformat(),
        "applied_at": now.isoformat(),
        "last_activity_at": now.isoformat(),
        "status": "active",
    }

    application = await client.insert("applications", app_data)

    # Create initial event
    event_data = {
        "tenant_id": str(current_user.tenant_id),
        "application_id": application["id"],
        "event_type": "application_created",
        "event_data": {
            "stage": application.get("current_stage"),
            "source": "manual",
        },
        "performed_by": str(current_user.user_id),
        "performed_at": now.isoformat(),
        "is_internal": True,
    }
    await client.insert("application_events", event_data)

    return ApplicationResponse(
        id=UUID(application["id"]),
        tenant_id=UUID(application["tenant_id"]),
        candidate_id=UUID(application["candidate_id"]),
        requisition_id=UUID(application["requisition_id"]),
        status=application.get("status", "active"),
        current_stage=application.get("current_stage", "Applied"),
        current_stage_id=UUID(application["current_stage_id"]) if application.get("current_stage_id") else None,
        stage_entered_at=datetime.fromisoformat(application["stage_entered_at"].replace("Z", "+00:00")) if application.get("stage_entered_at") else None,
        resume_id=UUID(application["resume_id"]) if application.get("resume_id") else None,
        cover_letter=application.get("cover_letter"),
        screening_answers=application.get("screening_answers") or {},
        recruiter_rating=application.get("recruiter_rating"),
        hiring_manager_rating=application.get("hiring_manager_rating"),
        overall_score=application.get("overall_score"),
        rejection_reason=application.get("rejection_reason"),
        rejection_notes=application.get("rejection_notes"),
        rejected_by=UUID(application["rejected_by"]) if application.get("rejected_by") else None,
        rejected_at=datetime.fromisoformat(application["rejected_at"].replace("Z", "+00:00")) if application.get("rejected_at") else None,
        offer_id=UUID(application["offer_id"]) if application.get("offer_id") else None,
        assigned_recruiter_id=UUID(application["assigned_recruiter_id"]) if application.get("assigned_recruiter_id") else None,
        applied_at=datetime.fromisoformat(application["applied_at"].replace("Z", "+00:00")) if application.get("applied_at") else None,
        last_activity_at=datetime.fromisoformat(application["last_activity_at"].replace("Z", "+00:00")) if application.get("last_activity_at") else None,
        created_at=datetime.fromisoformat(application["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(application["updated_at"].replace("Z", "+00:00")) if application.get("updated_at") else None,
    )


@router.get("/{application_id}", response_model=ApplicationWithCandidateResponse)
async def get_application(
    application_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get an application by ID."""
    client = get_supabase_client()

    # Get application with candidate data
    applications = await client.query(
        "applications",
        "*, candidates!applications_candidate_id_fkey(*)",
        filters={
            "id": str(application_id),
            "tenant_id": str(current_user.tenant_id),
        },
    )

    if not applications:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    app = applications[0]
    candidate = app.get("candidates") or {}

    return ApplicationWithCandidateResponse(
        id=UUID(app["id"]),
        tenant_id=UUID(app["tenant_id"]),
        candidate_id=UUID(app["candidate_id"]),
        requisition_id=UUID(app["requisition_id"]),
        status=app.get("status", "active"),
        current_stage=app.get("current_stage", "Applied"),
        current_stage_id=UUID(app["current_stage_id"]) if app.get("current_stage_id") else None,
        stage_entered_at=datetime.fromisoformat(app["stage_entered_at"].replace("Z", "+00:00")) if app.get("stage_entered_at") else None,
        resume_id=UUID(app["resume_id"]) if app.get("resume_id") else None,
        cover_letter=app.get("cover_letter"),
        screening_answers=app.get("screening_answers") or {},
        recruiter_rating=app.get("recruiter_rating"),
        hiring_manager_rating=app.get("hiring_manager_rating"),
        overall_score=app.get("overall_score"),
        rejection_reason=app.get("rejection_reason"),
        rejection_notes=app.get("rejection_notes"),
        rejected_by=UUID(app["rejected_by"]) if app.get("rejected_by") else None,
        rejected_at=datetime.fromisoformat(app["rejected_at"].replace("Z", "+00:00")) if app.get("rejected_at") else None,
        offer_id=UUID(app["offer_id"]) if app.get("offer_id") else None,
        assigned_recruiter_id=UUID(app["assigned_recruiter_id"]) if app.get("assigned_recruiter_id") else None,
        applied_at=datetime.fromisoformat(app["applied_at"].replace("Z", "+00:00")) if app.get("applied_at") else None,
        last_activity_at=datetime.fromisoformat(app["last_activity_at"].replace("Z", "+00:00")) if app.get("last_activity_at") else None,
        created_at=datetime.fromisoformat(app["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(app["updated_at"].replace("Z", "+00:00")) if app.get("updated_at") else None,
        candidate_name=f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or "Unknown",
        candidate_email=candidate.get("email", ""),
        candidate_phone=candidate.get("phone"),
    )


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: UUID,
    application_data: ApplicationUpdate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Update an application."""
    client = get_supabase_client()

    # Verify application exists
    app = await client.select(
        "applications",
        "*",
        filters={
            "id": str(application_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Apply updates
    update_data = application_data.model_dump(exclude_unset=True)
    update_data["last_activity_at"] = datetime.now(timezone.utc).isoformat()

    # Convert UUIDs to strings
    for key in ["resume_id", "assigned_recruiter_id", "current_stage_id"]:
        if key in update_data and update_data[key] is not None:
            update_data[key] = str(update_data[key])

    updated = await client.update(
        "applications",
        update_data,
        filters={"id": str(application_id)},
    )

    application = updated if updated else app

    return ApplicationResponse(
        id=UUID(application["id"]),
        tenant_id=UUID(application["tenant_id"]),
        candidate_id=UUID(application["candidate_id"]),
        requisition_id=UUID(application["requisition_id"]),
        status=application.get("status", "active"),
        current_stage=application.get("current_stage", "Applied"),
        current_stage_id=UUID(application["current_stage_id"]) if application.get("current_stage_id") else None,
        stage_entered_at=datetime.fromisoformat(application["stage_entered_at"].replace("Z", "+00:00")) if application.get("stage_entered_at") else None,
        resume_id=UUID(application["resume_id"]) if application.get("resume_id") else None,
        cover_letter=application.get("cover_letter"),
        screening_answers=application.get("screening_answers") or {},
        recruiter_rating=application.get("recruiter_rating"),
        hiring_manager_rating=application.get("hiring_manager_rating"),
        overall_score=application.get("overall_score"),
        rejection_reason=application.get("rejection_reason"),
        rejection_notes=application.get("rejection_notes"),
        rejected_by=UUID(application["rejected_by"]) if application.get("rejected_by") else None,
        rejected_at=datetime.fromisoformat(application["rejected_at"].replace("Z", "+00:00")) if application.get("rejected_at") else None,
        offer_id=UUID(application["offer_id"]) if application.get("offer_id") else None,
        assigned_recruiter_id=UUID(application["assigned_recruiter_id"]) if application.get("assigned_recruiter_id") else None,
        applied_at=datetime.fromisoformat(application["applied_at"].replace("Z", "+00:00")) if application.get("applied_at") else None,
        last_activity_at=datetime.fromisoformat(application["last_activity_at"].replace("Z", "+00:00")) if application.get("last_activity_at") else None,
        created_at=datetime.fromisoformat(application["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(application["updated_at"].replace("Z", "+00:00")) if application.get("updated_at") else None,
    )


@router.post("/{application_id}/stage", response_model=ApplicationResponse)
async def update_application_stage(
    application_id: UUID,
    stage_update: ApplicationStageUpdate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_MOVE_STAGE)),
):
    """Move application to a new stage."""
    client = get_supabase_client()

    # Get application
    app = await client.select(
        "applications",
        "*",
        filters={
            "id": str(application_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if app.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move stage on inactive application",
        )

    old_stage = app.get("current_stage")
    now = datetime.now(timezone.utc)

    # Update application
    update_data = {
        "current_stage": stage_update.stage,
        "current_stage_id": str(stage_update.stage_id) if stage_update.stage_id else None,
        "stage_entered_at": now.isoformat(),
        "last_activity_at": now.isoformat(),
    }

    updated = await client.update(
        "applications",
        update_data,
        filters={"id": str(application_id)},
    )

    # Create stage change event
    event_data = {
        "tenant_id": str(current_user.tenant_id),
        "application_id": str(application_id),
        "event_type": "stage_changed",
        "event_data": {
            "from_stage": old_stage,
            "to_stage": stage_update.stage,
            "notes": stage_update.notes,
        },
        "performed_by": str(current_user.user_id),
        "performed_at": now.isoformat(),
        "is_internal": True,
    }
    await client.insert("application_events", event_data)

    application = updated if updated else app

    return ApplicationResponse(
        id=UUID(application["id"]),
        tenant_id=UUID(application["tenant_id"]),
        candidate_id=UUID(application["candidate_id"]),
        requisition_id=UUID(application["requisition_id"]),
        status=application.get("status", "active"),
        current_stage=application.get("current_stage", "Applied"),
        current_stage_id=UUID(application["current_stage_id"]) if application.get("current_stage_id") else None,
        stage_entered_at=datetime.fromisoformat(application["stage_entered_at"].replace("Z", "+00:00")) if application.get("stage_entered_at") else None,
        resume_id=UUID(application["resume_id"]) if application.get("resume_id") else None,
        cover_letter=application.get("cover_letter"),
        screening_answers=application.get("screening_answers") or {},
        recruiter_rating=application.get("recruiter_rating"),
        hiring_manager_rating=application.get("hiring_manager_rating"),
        overall_score=application.get("overall_score"),
        rejection_reason=application.get("rejection_reason"),
        rejection_notes=application.get("rejection_notes"),
        rejected_by=UUID(application["rejected_by"]) if application.get("rejected_by") else None,
        rejected_at=datetime.fromisoformat(application["rejected_at"].replace("Z", "+00:00")) if application.get("rejected_at") else None,
        offer_id=UUID(application["offer_id"]) if application.get("offer_id") else None,
        assigned_recruiter_id=UUID(application["assigned_recruiter_id"]) if application.get("assigned_recruiter_id") else None,
        applied_at=datetime.fromisoformat(application["applied_at"].replace("Z", "+00:00")) if application.get("applied_at") else None,
        last_activity_at=datetime.fromisoformat(application["last_activity_at"].replace("Z", "+00:00")) if application.get("last_activity_at") else None,
        created_at=datetime.fromisoformat(application["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(application["updated_at"].replace("Z", "+00:00")) if application.get("updated_at") else None,
    )


@router.post("/{application_id}/reject", response_model=ApplicationResponse)
async def reject_application(
    application_id: UUID,
    rejection: ApplicationReject,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_REJECT)),
):
    """Reject an application."""
    client = get_supabase_client()

    # Get application
    app = await client.select(
        "applications",
        "*",
        filters={
            "id": str(application_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if app.get("status") == "rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application is already rejected",
        )

    now = datetime.now(timezone.utc)

    # Update application
    update_data = {
        "status": "rejected",
        "rejection_reason": rejection.rejection_reason,
        "rejection_notes": rejection.rejection_notes,
        "rejected_by": str(current_user.user_id),
        "rejected_at": now.isoformat(),
        "last_activity_at": now.isoformat(),
    }

    updated = await client.update(
        "applications",
        update_data,
        filters={"id": str(application_id)},
    )

    # Create rejection event
    event_data = {
        "tenant_id": str(current_user.tenant_id),
        "application_id": str(application_id),
        "event_type": "rejected",
        "event_data": {
            "reason": rejection.rejection_reason,
            "notes": rejection.rejection_notes,
            "stage_at_rejection": app.get("current_stage"),
        },
        "performed_by": str(current_user.user_id),
        "performed_at": now.isoformat(),
        "is_internal": True,
    }
    await client.insert("application_events", event_data)

    application = updated if updated else app

    return ApplicationResponse(
        id=UUID(application["id"]),
        tenant_id=UUID(application["tenant_id"]),
        candidate_id=UUID(application["candidate_id"]),
        requisition_id=UUID(application["requisition_id"]),
        status=application.get("status", "rejected"),
        current_stage=application.get("current_stage", "Applied"),
        current_stage_id=UUID(application["current_stage_id"]) if application.get("current_stage_id") else None,
        stage_entered_at=datetime.fromisoformat(application["stage_entered_at"].replace("Z", "+00:00")) if application.get("stage_entered_at") else None,
        resume_id=UUID(application["resume_id"]) if application.get("resume_id") else None,
        cover_letter=application.get("cover_letter"),
        screening_answers=application.get("screening_answers") or {},
        recruiter_rating=application.get("recruiter_rating"),
        hiring_manager_rating=application.get("hiring_manager_rating"),
        overall_score=application.get("overall_score"),
        rejection_reason=application.get("rejection_reason"),
        rejection_notes=application.get("rejection_notes"),
        rejected_by=UUID(application["rejected_by"]) if application.get("rejected_by") else None,
        rejected_at=datetime.fromisoformat(application["rejected_at"].replace("Z", "+00:00")) if application.get("rejected_at") else None,
        offer_id=UUID(application["offer_id"]) if application.get("offer_id") else None,
        assigned_recruiter_id=UUID(application["assigned_recruiter_id"]) if application.get("assigned_recruiter_id") else None,
        applied_at=datetime.fromisoformat(application["applied_at"].replace("Z", "+00:00")) if application.get("applied_at") else None,
        last_activity_at=datetime.fromisoformat(application["last_activity_at"].replace("Z", "+00:00")) if application.get("last_activity_at") else None,
        created_at=datetime.fromisoformat(application["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(application["updated_at"].replace("Z", "+00:00")) if application.get("updated_at") else None,
    )


@router.get("/{application_id}/events", response_model=list[ApplicationEventResponse])
async def get_application_events(
    application_id: UUID,
    include_internal: bool = Query(True),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get all events for an application."""
    client = get_supabase_client()

    # Verify application exists
    app = await client.select(
        "applications",
        "id",
        filters={
            "id": str(application_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Get events
    filters = {"application_id": str(application_id)}
    if not include_internal:
        filters["is_internal"] = "false"

    events = await client.query(
        "application_events",
        "*",
        filters=filters,
        order="performed_at",
        order_desc=True,
    )

    return [
        ApplicationEventResponse(
            id=UUID(e["id"]),
            tenant_id=UUID(e["tenant_id"]),
            application_id=UUID(e["application_id"]),
            event_type=e["event_type"],
            event_data=e.get("event_data") or {},
            performed_by=UUID(e["performed_by"]) if e.get("performed_by") else None,
            performed_at=datetime.fromisoformat(e["performed_at"].replace("Z", "+00:00")),
            is_internal=e.get("is_internal", True),
            created_at=datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")),
        )
        for e in events
    ]
