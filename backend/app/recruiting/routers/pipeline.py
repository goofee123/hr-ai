"""Pipeline router - Kanban view endpoints."""

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
from app.recruiting.models.candidate import Application, Candidate
from app.recruiting.models.job import JobRequisition, PipelineStage
from app.recruiting.schemas.application import (
    PipelineCandidate,
    PipelineResponse,
    PipelineStageWithCandidates,
)
from app.recruiting.schemas.job import PipelineStageCreate, PipelineStageResponse, PipelineStageUpdate

router = APIRouter()


@router.get("/jobs/{job_id}/pipeline", response_model=PipelineResponse)
async def get_job_pipeline(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get full pipeline view for a job requisition (Kanban data)."""
    # Get job requisition
    result = await db.execute(
        select(JobRequisition).where(
            JobRequisition.id == job_id,
            JobRequisition.tenant_id == tenant_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get pipeline stages
    result = await db.execute(
        select(PipelineStage)
        .where(PipelineStage.requisition_id == job_id)
        .order_by(PipelineStage.sort_order)
    )
    stages = result.scalars().all()

    # Get all active applications with candidates
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.candidate))
        .where(
            Application.requisition_id == job_id,
            Application.status == "active",
        )
        .order_by(Application.stage_entered_at)
    )
    applications = result.scalars().all()

    # Group applications by stage
    apps_by_stage: dict[str, list[Application]] = {}
    for app in applications:
        stage_name = app.current_stage
        if stage_name not in apps_by_stage:
            apps_by_stage[stage_name] = []
        apps_by_stage[stage_name].append(app)

    now = datetime.now(timezone.utc)

    # Build pipeline response
    pipeline_stages = []
    total_candidates = 0

    for stage in stages:
        stage_apps = apps_by_stage.get(stage.name, [])
        total_candidates += len(stage_apps)

        candidates = []
        for app in stage_apps:
            days_in_stage = (now - app.stage_entered_at).days if app.stage_entered_at else 0
            candidates.append(
                PipelineCandidate(
                    application_id=app.id,
                    candidate_id=app.candidate_id,
                    candidate_name=f"{app.candidate.first_name} {app.candidate.last_name}",
                    candidate_email=app.candidate.email,
                    current_stage=app.current_stage,
                    stage_entered_at=app.stage_entered_at,
                    applied_at=app.applied_at,
                    source=app.candidate.source,
                    recruiter_rating=app.recruiter_rating,
                    hiring_manager_rating=app.hiring_manager_rating,
                    days_in_stage=days_in_stage,
                )
            )

        pipeline_stages.append(
            PipelineStageWithCandidates(
                id=stage.id,
                name=stage.name,
                stage_type=stage.stage_type,
                sort_order=stage.sort_order,
                candidate_count=len(candidates),
                candidates=candidates,
            )
        )

    return PipelineResponse(
        requisition_id=job.id,
        requisition_number=job.requisition_number,
        external_title=job.external_title,
        total_candidates=total_candidates,
        stages=pipeline_stages,
    )


@router.get("/jobs/{job_id}/pipeline/summary")
async def get_pipeline_summary(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get pipeline summary statistics for a job."""
    # Verify job exists
    result = await db.execute(
        select(JobRequisition).where(
            JobRequisition.id == job_id,
            JobRequisition.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get stage counts
    result = await db.execute(
        select(
            Application.current_stage,
            func.count(Application.id).label("count"),
        )
        .where(
            Application.requisition_id == job_id,
            Application.status == "active",
        )
        .group_by(Application.current_stage)
    )
    stage_counts = {row.current_stage: row.count for row in result}

    # Get status counts
    result = await db.execute(
        select(
            Application.status,
            func.count(Application.id).label("count"),
        )
        .where(Application.requisition_id == job_id)
        .group_by(Application.status)
    )
    status_counts = {row.status: row.count for row in result}

    # Get total applications
    total = sum(status_counts.values())

    return {
        "total_applications": total,
        "active": status_counts.get("active", 0),
        "rejected": status_counts.get("rejected", 0),
        "withdrawn": status_counts.get("withdrawn", 0),
        "hired": status_counts.get("hired", 0),
        "by_stage": stage_counts,
    }


@router.post("/jobs/{job_id}/stages", response_model=PipelineStageResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_stage(
    job_id: UUID,
    stage_data: PipelineStageCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Add a new pipeline stage to a job."""
    # Verify job exists
    result = await db.execute(
        select(JobRequisition).where(
            JobRequisition.id == job_id,
            JobRequisition.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Check for duplicate stage name
    result = await db.execute(
        select(PipelineStage).where(
            PipelineStage.requisition_id == job_id,
            PipelineStage.name == stage_data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stage with this name already exists",
        )

    # Get max sort order
    result = await db.execute(
        select(func.max(PipelineStage.sort_order))
        .where(PipelineStage.requisition_id == job_id)
    )
    max_order = result.scalar() or 0

    # Create stage
    stage = PipelineStage(
        tenant_id=tenant_id,
        requisition_id=job_id,
        name=stage_data.name,
        stage_type=stage_data.stage_type,
        sort_order=stage_data.sort_order or (max_order + 1),
        is_rejection_stage=stage_data.is_rejection_stage,
        requires_feedback=stage_data.requires_feedback,
        interview_required=stage_data.interview_required,
    )

    db.add(stage)
    await db.commit()
    await db.refresh(stage)

    return PipelineStageResponse.model_validate(stage)


@router.patch("/stages/{stage_id}", response_model=PipelineStageResponse)
async def update_pipeline_stage(
    stage_id: UUID,
    stage_data: PipelineStageUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Update a pipeline stage."""
    result = await db.execute(
        select(PipelineStage).where(
            PipelineStage.id == stage_id,
            PipelineStage.tenant_id == tenant_id,
        )
    )
    stage = result.scalar_one_or_none()

    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline stage not found",
        )

    # Check for name conflict if changing name
    if stage_data.name and stage_data.name != stage.name:
        result = await db.execute(
            select(PipelineStage).where(
                PipelineStage.requisition_id == stage.requisition_id,
                PipelineStage.name == stage_data.name,
                PipelineStage.id != stage_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another stage with this name already exists",
            )

    # Apply updates
    update_data = stage_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(stage, field, value)

    await db.commit()
    await db.refresh(stage)

    return PipelineStageResponse.model_validate(stage)


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_stage(
    stage_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Delete a pipeline stage."""
    result = await db.execute(
        select(PipelineStage).where(
            PipelineStage.id == stage_id,
            PipelineStage.tenant_id == tenant_id,
        )
    )
    stage = result.scalar_one_or_none()

    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline stage not found",
        )

    # Check if any applications are in this stage
    result = await db.execute(
        select(func.count(Application.id))
        .where(Application.current_stage_id == stage_id)
    )
    app_count = result.scalar() or 0

    if app_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete stage with {app_count} active applications",
        )

    await db.delete(stage)
    await db.commit()

    return None


@router.post("/stages/reorder")
async def reorder_pipeline_stages(
    job_id: UUID = Query(...),
    stage_ids: list[UUID] = Query(...),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Reorder pipeline stages."""
    # Verify job exists
    result = await db.execute(
        select(JobRequisition).where(
            JobRequisition.id == job_id,
            JobRequisition.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get all stages for this job
    result = await db.execute(
        select(PipelineStage).where(PipelineStage.requisition_id == job_id)
    )
    stages = {s.id: s for s in result.scalars().all()}

    # Verify all stage IDs are valid
    for stage_id in stage_ids:
        if stage_id not in stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stage {stage_id} not found for this job",
            )

    # Update sort orders
    for index, stage_id in enumerate(stage_ids):
        stages[stage_id].sort_order = index + 1

    await db.commit()

    return {"message": "Stages reordered successfully"}
