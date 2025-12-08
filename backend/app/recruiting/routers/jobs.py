"""Job requisitions router - using Supabase REST API."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission, require_any_permission
from app.core.security import TokenData, get_current_user
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.job import (
    JobRequisitionCreate,
    JobRequisitionUpdate,
    JobRequisitionResponse,
    JobRequisitionListResponse,
    RequisitionStatusUpdate,
    PipelineStageResponse,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


# Default pipeline stages
DEFAULT_PIPELINE_STAGES = [
    {"name": "Applied", "stage_type": "initial", "sort_order": 1},
    {"name": "Screening", "stage_type": "screen", "sort_order": 2},
    {"name": "Phone Interview", "stage_type": "interview", "sort_order": 3, "interview_required": True},
    {"name": "On-site Interview", "stage_type": "interview", "sort_order": 4, "interview_required": True, "requires_feedback": True},
    {"name": "Offer", "stage_type": "offer", "sort_order": 5},
    {"name": "Hired", "stage_type": "hired", "sort_order": 6},
]


@router.get("", response_model=PaginatedResponse[JobRequisitionListResponse])
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    department_id: Optional[UUID] = None,
    hiring_manager_id: Optional[UUID] = None,
    recruiter_id: Optional[UUID] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(require_any_permission(
        Permission.JOBS_VIEW, Permission.JOBS_CREATE
    )),
):
    """List job requisitions with filters and pagination."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}
    if status:
        filters["status"] = status
    if department_id:
        filters["department_id"] = str(department_id)
    if hiring_manager_id:
        filters["hiring_manager_id"] = str(hiring_manager_id)
    if recruiter_id:
        filters["primary_recruiter_id"] = str(recruiter_id)

    # Get all jobs (we'll filter search in Python for now)
    jobs = await client.select("job_requisitions", "*", filters=filters) or []

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        jobs = [
            j for j in jobs
            if search_lower in j.get("external_title", "").lower()
            or search_lower in j.get("requisition_number", "").lower()
        ]

    # Get total count before pagination
    total = len(jobs)

    # Sort by created_at descending
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Apply pagination
    offset = (page - 1) * page_size
    jobs = jobs[offset:offset + page_size]

    # Get candidate counts for each job
    job_ids = [j["id"] for j in jobs]
    counts = {}
    if job_ids:
        for job_id in job_ids:
            applications = await client.select(
                "applications",
                "id",
                filters={"requisition_id": job_id}
            ) or []
            counts[job_id] = len(applications)

    # Build response with candidate counts
    items = []
    for job in jobs:
        response = JobRequisitionListResponse.model_validate(job)
        response.candidate_count = counts.get(job["id"], 0)
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=JobRequisitionResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobRequisitionCreate,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_CREATE)),
):
    """Create a new job requisition."""
    client = get_supabase_client()

    # Prepare job data
    job_dict = {
        "tenant_id": str(current_user.tenant_id),
        "external_title": job_data.external_title,
        "internal_title": job_data.internal_title,
        "internal_title_id": str(job_data.internal_title_id) if job_data.internal_title_id else None,
        "job_description": job_data.job_description,
        "requirements": job_data.requirements,
        "department_id": str(job_data.department_id) if job_data.department_id else None,
        "location_id": str(job_data.location_id) if job_data.location_id else None,
        "reports_to_id": str(job_data.reports_to_id) if job_data.reports_to_id else None,
        "pay_grade_id": str(job_data.pay_grade_id) if job_data.pay_grade_id else None,
        "salary_min": float(job_data.salary_min) if job_data.salary_min else None,
        "salary_max": float(job_data.salary_max) if job_data.salary_max else None,
        "target_salary": float(job_data.target_salary) if job_data.target_salary else None,
        "is_salary_visible": job_data.is_salary_visible,
        "positions_approved": job_data.positions_approved,
        "worker_type": job_data.worker_type,
        "hiring_manager_id": str(job_data.hiring_manager_id) if job_data.hiring_manager_id else None,
        "primary_recruiter_id": str(job_data.primary_recruiter_id) if job_data.primary_recruiter_id else None,
        "target_fill_date": job_data.target_fill_date.isoformat() if job_data.target_fill_date else None,
        "sla_days": job_data.sla_days,
        "template_id": str(job_data.template_id) if job_data.template_id else None,
        "status": "draft",
        "created_by": str(current_user.user_id),
    }

    # Create job
    job = await client.insert("job_requisitions", job_dict)

    # Create pipeline stages
    stages_config = job_data.pipeline_stages or DEFAULT_PIPELINE_STAGES
    for stage_config in stages_config:
        stage_dict = {
            "tenant_id": str(current_user.tenant_id),
            "requisition_id": job["id"],
            "name": stage_config.get("name") if isinstance(stage_config, dict) else stage_config.name,
            "stage_type": stage_config.get("stage_type", "standard") if isinstance(stage_config, dict) else stage_config.stage_type,
            "sort_order": stage_config.get("sort_order", 0) if isinstance(stage_config, dict) else stage_config.sort_order,
            "is_rejection_stage": stage_config.get("is_rejection_stage", False) if isinstance(stage_config, dict) else getattr(stage_config, 'is_rejection_stage', False),
            "requires_feedback": stage_config.get("requires_feedback", False) if isinstance(stage_config, dict) else getattr(stage_config, 'requires_feedback', False),
            "interview_required": stage_config.get("interview_required", False) if isinstance(stage_config, dict) else getattr(stage_config, 'interview_required', False),
        }
        await client.insert("pipeline_stages", stage_dict)

    return JobRequisitionResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobRequisitionResponse)
async def get_job(
    job_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get a job requisition by ID."""
    client = get_supabase_client()

    job = await client.select(
        "job_requisitions",
        "*",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    return JobRequisitionResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobRequisitionResponse)
async def update_job(
    job_id: UUID,
    job_data: JobRequisitionUpdate,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Update a job requisition."""
    client = get_supabase_client()

    # Check job exists
    job = await client.select(
        "job_requisitions",
        "*",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Apply updates
    update_data = job_data.model_dump(exclude_unset=True)
    if update_data:
        # Convert UUIDs to strings
        for key, value in update_data.items():
            if isinstance(value, UUID):
                update_data[key] = str(value)

        job = await client.update(
            "job_requisitions",
            update_data,
            filters={"id": str(job_id)},
        )

    return JobRequisitionResponse.model_validate(job)


@router.post("/{job_id}/status", response_model=JobRequisitionResponse)
async def update_job_status(
    job_id: UUID,
    status_update: RequisitionStatusUpdate,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_CHANGE_STATUS)),
):
    """Update job requisition status."""
    client = get_supabase_client()

    # Get current job
    job = await client.select(
        "job_requisitions",
        "*",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Prepare update
    old_status = job["status"]
    new_status = status_update.status
    now = datetime.now(timezone.utc).isoformat()

    update_data = {"status": new_status}

    # Set timestamps based on status
    if new_status == "open" and old_status != "open":
        update_data["opened_at"] = now
        update_data["approved_by"] = str(current_user.user_id)
        update_data["approved_at"] = now
    elif new_status in ("closed_filled", "closed_cancelled"):
        update_data["closed_at"] = now

    job = await client.update(
        "job_requisitions",
        update_data,
        filters={"id": str(job_id)},
    )

    return JobRequisitionResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_DELETE)),
):
    """Delete (archive) a job requisition."""
    client = get_supabase_client()

    # Check job exists
    job = await client.select(
        "job_requisitions",
        "*",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Soft delete by setting status
    now = datetime.now(timezone.utc).isoformat()
    await client.update(
        "job_requisitions",
        {"status": "closed_cancelled", "closed_at": now},
        filters={"id": str(job_id)},
    )

    return None


@router.get("/{job_id}/stages", response_model=list[PipelineStageResponse])
async def get_job_stages(
    job_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get pipeline stages for a job requisition."""
    client = get_supabase_client()

    # Verify job exists
    job = await client.select(
        "job_requisitions",
        "id",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get stages
    stages = await client.select(
        "pipeline_stages",
        "*",
        filters={"requisition_id": str(job_id)},
    ) or []

    # Sort by sort_order
    stages.sort(key=lambda x: x.get("sort_order", 0))

    return [PipelineStageResponse.model_validate(s) for s in stages]
