"""Applications router."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.tenant import get_tenant_id
from app.recruiting.models.candidate import Application, ApplicationEvent, Candidate
from app.recruiting.models.job import JobRequisition, PipelineStage
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
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List applications with filters."""
    # Base query with candidate join
    query = (
        select(Application)
        .options(selectinload(Application.candidate))
        .where(Application.tenant_id == tenant_id)
    )

    # Apply filters
    if requisition_id:
        query = query.where(Application.requisition_id == requisition_id)
    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
    if status:
        query = query.where(Application.status == status)
    if stage:
        query = query.where(Application.current_stage == stage)
    if assigned_recruiter_id:
        query = query.where(Application.assigned_recruiter_id == assigned_recruiter_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Application.applied_at.desc())

    result = await db.execute(query)
    applications = result.scalars().all()

    # Build response with candidate info
    items = []
    for app in applications:
        response = ApplicationWithCandidateResponse(
            id=app.id,
            tenant_id=app.tenant_id,
            candidate_id=app.candidate_id,
            requisition_id=app.requisition_id,
            status=app.status,
            current_stage=app.current_stage,
            current_stage_id=app.current_stage_id,
            stage_entered_at=app.stage_entered_at,
            resume_id=app.resume_id,
            cover_letter=app.cover_letter,
            screening_answers=app.screening_answers or {},
            recruiter_rating=app.recruiter_rating,
            hiring_manager_rating=app.hiring_manager_rating,
            overall_score=app.overall_score,
            rejection_reason=app.rejection_reason,
            rejection_notes=app.rejection_notes,
            rejected_by=app.rejected_by,
            rejected_at=app.rejected_at,
            offer_id=app.offer_id,
            assigned_recruiter_id=app.assigned_recruiter_id,
            applied_at=app.applied_at,
            last_activity_at=app.last_activity_at,
            created_at=app.created_at,
            updated_at=app.updated_at,
            candidate_name=f"{app.candidate.first_name} {app.candidate.last_name}",
            candidate_email=app.candidate.email,
            candidate_phone=app.candidate.phone,
        )
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_CREATE)),
):
    """Create a new application."""
    # Verify candidate exists
    result = await db.execute(
        select(Candidate).where(
            Candidate.id == application_data.candidate_id,
            Candidate.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Verify requisition exists and is open
    result = await db.execute(
        select(JobRequisition).where(
            JobRequisition.id == application_data.requisition_id,
            JobRequisition.tenant_id == tenant_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )
    if job.status not in ("open", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job requisition is not accepting applications",
        )

    # Check for existing application
    result = await db.execute(
        select(Application).where(
            Application.tenant_id == tenant_id,
            Application.candidate_id == application_data.candidate_id,
            Application.requisition_id == application_data.requisition_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate already applied for this position",
        )

    # Get initial stage
    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.requisition_id == application_data.requisition_id)
        .order_by(PipelineStage.sort_order)
        .limit(1)
    )
    initial_stage = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    # Create application
    application = Application(
        tenant_id=tenant_id,
        candidate_id=application_data.candidate_id,
        requisition_id=application_data.requisition_id,
        resume_id=application_data.resume_id,
        cover_letter=application_data.cover_letter,
        screening_answers=application_data.screening_answers or {},
        assigned_recruiter_id=application_data.assigned_recruiter_id or job.primary_recruiter_id,
        current_stage=initial_stage.name if initial_stage else "Applied",
        current_stage_id=initial_stage.id if initial_stage else None,
        stage_entered_at=now,
        applied_at=now,
        last_activity_at=now,
        status="active",
    )

    db.add(application)
    await db.flush()

    # Create initial event
    event = ApplicationEvent(
        tenant_id=tenant_id,
        application_id=application.id,
        event_type="application_created",
        event_data={
            "stage": application.current_stage,
            "source": "manual",
        },
        performed_by=current_user.user_id,
        performed_at=now,
        is_internal=True,
    )
    db.add(event)

    await db.commit()
    await db.refresh(application)

    return ApplicationResponse.model_validate(application)


@router.get("/{application_id}", response_model=ApplicationWithCandidateResponse)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get an application by ID."""
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.candidate))
        .where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return ApplicationWithCandidateResponse(
        id=application.id,
        tenant_id=application.tenant_id,
        candidate_id=application.candidate_id,
        requisition_id=application.requisition_id,
        status=application.status,
        current_stage=application.current_stage,
        current_stage_id=application.current_stage_id,
        stage_entered_at=application.stage_entered_at,
        resume_id=application.resume_id,
        cover_letter=application.cover_letter,
        screening_answers=application.screening_answers or {},
        recruiter_rating=application.recruiter_rating,
        hiring_manager_rating=application.hiring_manager_rating,
        overall_score=application.overall_score,
        rejection_reason=application.rejection_reason,
        rejection_notes=application.rejection_notes,
        rejected_by=application.rejected_by,
        rejected_at=application.rejected_at,
        offer_id=application.offer_id,
        assigned_recruiter_id=application.assigned_recruiter_id,
        applied_at=application.applied_at,
        last_activity_at=application.last_activity_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
        candidate_name=f"{application.candidate.first_name} {application.candidate.last_name}",
        candidate_email=application.candidate.email,
        candidate_phone=application.candidate.phone,
    )


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: UUID,
    application_data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Update an application."""
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Apply updates
    update_data = application_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(application, field, value)

    application.last_activity_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(application)

    return ApplicationResponse.model_validate(application)


@router.post("/{application_id}/stage", response_model=ApplicationResponse)
async def update_application_stage(
    application_id: UUID,
    stage_update: ApplicationStageUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_MOVE_STAGE)),
):
    """Move application to a new stage."""
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if application.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move stage on inactive application",
        )

    old_stage = application.current_stage
    now = datetime.now(timezone.utc)

    # Update stage
    application.current_stage = stage_update.stage
    application.current_stage_id = stage_update.stage_id
    application.stage_entered_at = now
    application.last_activity_at = now

    # Create stage change event
    event = ApplicationEvent(
        tenant_id=tenant_id,
        application_id=application.id,
        event_type="stage_changed",
        event_data={
            "from_stage": old_stage,
            "to_stage": stage_update.stage,
            "notes": stage_update.notes,
        },
        performed_by=current_user.user_id,
        performed_at=now,
        is_internal=True,
    )
    db.add(event)

    await db.commit()
    await db.refresh(application)

    return ApplicationResponse.model_validate(application)


@router.post("/{application_id}/reject", response_model=ApplicationResponse)
async def reject_application(
    application_id: UUID,
    rejection: ApplicationReject,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_REJECT)),
):
    """Reject an application."""
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if application.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application is already rejected",
        )

    now = datetime.now(timezone.utc)

    # Update application
    application.status = "rejected"
    application.rejection_reason = rejection.rejection_reason
    application.rejection_notes = rejection.rejection_notes
    application.rejected_by = current_user.user_id
    application.rejected_at = now
    application.last_activity_at = now

    # Create rejection event
    event = ApplicationEvent(
        tenant_id=tenant_id,
        application_id=application.id,
        event_type="rejected",
        event_data={
            "reason": rejection.rejection_reason,
            "notes": rejection.rejection_notes,
            "stage_at_rejection": application.current_stage,
        },
        performed_by=current_user.user_id,
        performed_at=now,
        is_internal=True,
    )
    db.add(event)

    await db.commit()
    await db.refresh(application)

    return ApplicationResponse.model_validate(application)


@router.get("/{application_id}/events", response_model=list[ApplicationEventResponse])
async def get_application_events(
    application_id: UUID,
    include_internal: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get all events for an application."""
    # Verify application exists
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Get events
    query = select(ApplicationEvent).where(
        ApplicationEvent.application_id == application_id
    )
    if not include_internal:
        query = query.where(ApplicationEvent.is_internal == False)

    query = query.order_by(ApplicationEvent.performed_at.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    return [ApplicationEventResponse.model_validate(e) for e in events]
