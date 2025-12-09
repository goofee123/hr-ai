"""Pipeline router - Kanban view endpoints using Supabase REST API."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.tenant import get_tenant_id
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.application import (
    PipelineCandidate,
    PipelineResponse,
    PipelineStageWithCandidates,
)
from app.recruiting.schemas.job import PipelineStageCreate, PipelineStageResponse, PipelineStageUpdate

router = APIRouter()


@router.get("/jobs/overview")
async def get_jobs_overview(
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get overview of all jobs with pipeline summary."""
    from app.config import get_settings
    import httpx

    settings = get_settings()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as http_client:
        # Get all open jobs
        jobs_response = await http_client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=headers,
            params={
                "select": "id,requisition_number,external_title,status,department,location",
                "tenant_id": f"eq.{tenant_id}",
                "status": "eq.open",
                "order": "created_at.desc",
            },
            timeout=15,
        )
        jobs = jobs_response.json() if jobs_response.status_code == 200 else []

        # Get application counts
        apps_response = await http_client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=headers,
            params={
                "select": "requisition_id,status,current_stage",
                "tenant_id": f"eq.{tenant_id}",
            },
            timeout=15,
        )
        applications = apps_response.json() if apps_response.status_code == 200 else []

    # Group by job
    job_stats = {}
    for app in applications:
        req_id = app.get("requisition_id")
        if req_id not in job_stats:
            job_stats[req_id] = {"total": 0, "active": 0, "by_stage": {}}
        job_stats[req_id]["total"] += 1
        if app.get("status") == "active":
            job_stats[req_id]["active"] += 1
            stage = app.get("current_stage", "Applied")
            job_stats[req_id]["by_stage"][stage] = job_stats[req_id]["by_stage"].get(stage, 0) + 1

    # Build response
    result = []
    for job in jobs:
        stats = job_stats.get(job["id"], {"total": 0, "active": 0, "by_stage": {}})
        result.append({
            "id": job["id"],
            "requisition_number": job.get("requisition_number"),
            "external_title": job.get("external_title"),
            "status": job.get("status"),
            "department": job.get("department"),
            "location": job.get("location"),
            "total_applications": stats["total"],
            "active_applications": stats["active"],
            "pipeline_breakdown": stats["by_stage"],
        })

    return {"jobs": result, "total": len(result)}


@router.get("/jobs/{job_id}/pipeline", response_model=PipelineResponse)
async def get_job_pipeline(
    job_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get full pipeline view for a job requisition (Kanban data)."""
    client = get_supabase_client()

    # Get job requisition
    job = await client.select(
        "job_requisitions",
        "*",
        filters={"id": str(job_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get pipeline stages ordered by sort_order
    stages = await client.query(
        "pipeline_stages",
        "*",
        filters={"requisition_id": str(job_id)},
        order="sort_order",
    )

    # Get applications with candidate info using PostgREST embedded resources
    # Format: applications with candidate data embedded
    applications = await client.query(
        "applications",
        "*, candidates!applications_candidate_id_fkey(*)",
        filters={"requisition_id": str(job_id)},
        order="stage_entered_at",
    )

    # Group applications by stage
    apps_by_stage: dict[str, list[dict]] = {}
    for app in applications:
        stage_name = app.get("current_stage", "Applied")
        if stage_name not in apps_by_stage:
            apps_by_stage[stage_name] = []
        apps_by_stage[stage_name].append(app)

    now = datetime.now(timezone.utc)

    # Build pipeline response
    pipeline_stages = []
    total_candidates = 0

    for stage in stages:
        stage_apps = apps_by_stage.get(stage["name"], [])
        total_candidates += len(stage_apps)

        candidates = []
        for app in stage_apps:
            candidate = app.get("candidates") or {}
            stage_entered = app.get("stage_entered_at")
            if stage_entered:
                try:
                    entered_dt = datetime.fromisoformat(stage_entered.replace("Z", "+00:00"))
                    days_in_stage = (now - entered_dt).days
                except (ValueError, TypeError):
                    days_in_stage = 0
            else:
                days_in_stage = 0

            applied_at = app.get("applied_at")
            if applied_at:
                try:
                    applied_dt = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    applied_dt = None
            else:
                applied_dt = None

            candidates.append(
                PipelineCandidate(
                    application_id=UUID(app["id"]),
                    candidate_id=UUID(app["candidate_id"]),
                    candidate_name=f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip() or "Unknown",
                    candidate_email=candidate.get("email", ""),
                    current_stage=app.get("current_stage", "Applied"),
                    stage_entered_at=datetime.fromisoformat(stage_entered.replace("Z", "+00:00")) if stage_entered else None,
                    applied_at=applied_dt,
                    source=candidate.get("source"),
                    recruiter_rating=app.get("recruiter_rating"),
                    hiring_manager_rating=app.get("hiring_manager_rating"),
                    days_in_stage=days_in_stage,
                )
            )

        pipeline_stages.append(
            PipelineStageWithCandidates(
                id=UUID(stage["id"]),
                name=stage["name"],
                stage_type=stage.get("stage_type", "standard"),
                sort_order=stage["sort_order"],
                candidate_count=len(candidates),
                candidates=candidates,
            )
        )

    return PipelineResponse(
        requisition_id=UUID(job["id"]),
        requisition_number=job["requisition_number"],
        external_title=job["external_title"],
        total_candidates=total_candidates,
        stages=pipeline_stages,
    )


@router.get("/jobs/{job_id}/pipeline/summary")
async def get_pipeline_summary(
    job_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get pipeline summary statistics for a job."""
    client = get_supabase_client()

    # Verify job exists
    job = await client.select(
        "job_requisitions",
        "id",
        filters={"id": str(job_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get all applications for this job
    applications = await client.query(
        "applications",
        "id, current_stage, status",
        filters={"requisition_id": str(job_id)},
    )

    # Count by stage (for active applications)
    stage_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    for app in applications:
        status_val = app.get("status", "new")
        status_counts[status_val] = status_counts.get(status_val, 0) + 1

        # Only count stages for non-terminal statuses
        if status_val not in ["rejected", "withdrawn", "hired"]:
            stage = app.get("current_stage", "Applied")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

    total = len(applications)

    return {
        "total_applications": total,
        "active": sum(1 for app in applications if app.get("status") not in ["rejected", "withdrawn", "hired"]),
        "rejected": status_counts.get("rejected", 0),
        "withdrawn": status_counts.get("withdrawn", 0),
        "hired": status_counts.get("hired", 0),
        "by_stage": stage_counts,
    }


@router.post("/jobs/{job_id}/stages", response_model=PipelineStageResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline_stage(
    job_id: UUID,
    stage_data: PipelineStageCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Add a new pipeline stage to a job."""
    client = get_supabase_client()

    # Verify job exists
    job = await client.select(
        "job_requisitions",
        "id",
        filters={"id": str(job_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Check for duplicate stage name
    existing = await client.select(
        "pipeline_stages",
        "id",
        filters={"requisition_id": str(job_id), "name": stage_data.name},
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stage with this name already exists",
        )

    # Get max sort order
    stages = await client.query(
        "pipeline_stages",
        "sort_order",
        filters={"requisition_id": str(job_id)},
        order="sort_order",
        order_desc=True,
        limit=1,
    )
    max_order = stages[0]["sort_order"] if stages else 0

    # Create stage
    stage = await client.insert(
        "pipeline_stages",
        {
            "tenant_id": str(tenant_id),
            "requisition_id": str(job_id),
            "name": stage_data.name,
            "stage_type": stage_data.stage_type,
            "sort_order": stage_data.sort_order or (max_order + 1),
            "is_rejection_stage": stage_data.is_rejection_stage,
            "requires_feedback": stage_data.requires_feedback,
            "interview_required": stage_data.interview_required,
        },
    )

    return PipelineStageResponse(
        id=UUID(stage["id"]),
        requisition_id=UUID(stage["requisition_id"]),
        name=stage["name"],
        stage_type=stage.get("stage_type", "standard"),
        sort_order=stage["sort_order"],
        is_rejection_stage=stage.get("is_rejection_stage", False),
        requires_feedback=stage.get("requires_feedback", False),
        interview_required=stage.get("interview_required", False),
        candidate_count=stage.get("candidate_count", 0),
    )


@router.patch("/stages/{stage_id}", response_model=PipelineStageResponse)
async def update_pipeline_stage(
    stage_id: UUID,
    stage_data: PipelineStageUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Update a pipeline stage."""
    client = get_supabase_client()

    # Get current stage
    stage = await client.select(
        "pipeline_stages",
        "*",
        filters={"id": str(stage_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline stage not found",
        )

    # Check for name conflict if changing name
    if stage_data.name and stage_data.name != stage["name"]:
        existing = await client.query(
            "pipeline_stages",
            "id",
            filters={"requisition_id": stage["requisition_id"], "name": stage_data.name},
        )
        # Filter out current stage
        existing = [s for s in existing if s["id"] != str(stage_id)]
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another stage with this name already exists",
            )

    # Apply updates
    update_data = stage_data.model_dump(exclude_unset=True)
    if update_data:
        updated = await client.update(
            "pipeline_stages",
            update_data,
            filters={"id": str(stage_id)},
        )
        if updated:
            stage = updated

    return PipelineStageResponse(
        id=UUID(stage["id"]),
        requisition_id=UUID(stage["requisition_id"]),
        name=stage["name"],
        stage_type=stage.get("stage_type", "standard"),
        sort_order=stage["sort_order"],
        is_rejection_stage=stage.get("is_rejection_stage", False),
        requires_feedback=stage.get("requires_feedback", False),
        interview_required=stage.get("interview_required", False),
        candidate_count=stage.get("candidate_count", 0),
    )


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_stage(
    stage_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Delete a pipeline stage."""
    client = get_supabase_client()

    # Get stage
    stage = await client.select(
        "pipeline_stages",
        "*",
        filters={"id": str(stage_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline stage not found",
        )

    # Check if any applications are in this stage
    apps = await client.query(
        "applications",
        "id",
        filters={"current_stage_id": str(stage_id)},
        limit=1,
    )

    if apps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete stage with active applications",
        )

    await client.delete("pipeline_stages", filters={"id": str(stage_id)})

    return None


@router.post("/stages/reorder")
async def reorder_pipeline_stages(
    job_id: UUID = Query(...),
    stage_ids: list[UUID] = Query(...),
    tenant_id: UUID = Depends(get_tenant_id),
    _: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Reorder pipeline stages."""
    client = get_supabase_client()

    # Verify job exists
    job = await client.select(
        "job_requisitions",
        "id",
        filters={"id": str(job_id), "tenant_id": str(tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get all stages for this job
    stages = await client.query(
        "pipeline_stages",
        "id",
        filters={"requisition_id": str(job_id)},
    )
    stage_id_set = {s["id"] for s in stages}

    # Verify all stage IDs are valid
    for stage_id in stage_ids:
        if str(stage_id) not in stage_id_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stage {stage_id} not found for this job",
            )

    # Update sort orders
    for index, stage_id in enumerate(stage_ids):
        await client.update(
            "pipeline_stages",
            {"sort_order": index + 1},
            filters={"id": str(stage_id)},
        )

    return {"message": "Stages reordered successfully"}
