"""Recruiter assignments router - using Supabase REST API."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission, require_any_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.assignment import (
    RecruiterAssignmentCreate,
    RecruiterAssignmentResponse,
    RecruiterAssignmentListResponse,
    RecruiterReassign,
    MyAssignmentsResponse,
    SLAAlertResponse,
    AcknowledgeAlertRequest,
)
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


def calculate_sla_status(sla_deadline: Optional[datetime], amber_percent: int = 75, red_percent: int = 90) -> tuple[Optional[int], Optional[str]]:
    """Calculate days remaining and SLA status (green/amber/red)."""
    if not sla_deadline:
        return None, None

    now = datetime.now(timezone.utc)
    if sla_deadline.tzinfo is None:
        sla_deadline = sla_deadline.replace(tzinfo=timezone.utc)

    delta = sla_deadline - now
    days_remaining = delta.days

    if days_remaining < 0:
        return days_remaining, "red"

    # Calculate percentage of time elapsed
    # We need the original SLA days to calculate this properly
    # For now, use days_remaining as a proxy
    if days_remaining <= 2:
        return days_remaining, "red"
    elif days_remaining <= 5:
        return days_remaining, "amber"
    else:
        return days_remaining, "green"


@router.get("/jobs/{job_id}/assignments", response_model=list[RecruiterAssignmentListResponse])
async def get_job_assignments(
    job_id: UUID,
    include_inactive: bool = Query(False, description="Include reassigned/completed assignments"),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get all recruiter assignments for a job requisition."""
    client = get_supabase_client()

    # Verify job exists
    job = await client.select(
        "job_requisitions",
        "id,external_title,requisition_number",
        filters={"id": str(job_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    # Get assignments
    filters = {
        "requisition_id": str(job_id),
        "tenant_id": str(current_user.tenant_id),
    }
    if not include_inactive:
        filters["status"] = "active"

    assignments = await client.select("recruiter_assignments", "*", filters=filters) or []

    # Get recruiter names
    recruiter_ids = list(set(a["recruiter_id"] for a in assignments if a.get("recruiter_id")))
    recruiters = {}
    for rid in recruiter_ids:
        user = await client.select("users", "id,full_name,email", filters={"id": rid}, single=True)
        if user:
            recruiters[rid] = user.get('full_name', '')

    # Build response
    result = []
    for assignment in assignments:
        days_remaining, sla_status = calculate_sla_status(
            datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00")) if assignment.get("sla_deadline") else None
        )
        result.append(RecruiterAssignmentListResponse(
            id=UUID(assignment["id"]),
            requisition_id=UUID(assignment["requisition_id"]),
            recruiter_id=UUID(assignment["recruiter_id"]),
            assigned_at=datetime.fromisoformat(assignment["assigned_at"].replace("Z", "+00:00")),
            sla_days=assignment.get("sla_days"),
            sla_deadline=datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00")) if assignment.get("sla_deadline") else None,
            status=assignment["status"],
            days_remaining=days_remaining,
            sla_status=sla_status,
            recruiter_name=recruiters.get(assignment["recruiter_id"]),
            job_title=job.get("external_title"),
            requisition_number=job.get("requisition_number"),
        ))

    # Sort by assigned_at descending
    result.sort(key=lambda x: x.assigned_at, reverse=True)

    return result


@router.post("/jobs/{job_id}/assign", response_model=RecruiterAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_recruiter(
    job_id: UUID,
    assignment_data: RecruiterAssignmentCreate,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Assign a recruiter to a job requisition."""
    client = get_supabase_client()

    # Verify job exists
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

    # Verify recruiter exists and is in same tenant
    recruiter = await client.select(
        "users",
        "id,full_name,email,tenant_id",
        filters={"id": str(assignment_data.recruiter_id)},
        single=True,
    )

    if not recruiter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recruiter not found",
        )

    if recruiter["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign recruiter from different tenant",
        )

    # Check if recruiter already has an active assignment for this job
    existing = await client.select(
        "recruiter_assignments",
        "id",
        filters={
            "requisition_id": str(job_id),
            "recruiter_id": str(assignment_data.recruiter_id),
            "status": "active",
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recruiter already has an active assignment for this job",
        )

    # Get default SLA configuration
    sla_days = assignment_data.sla_days
    if not sla_days:
        sla_config = await client.select(
            "sla_configurations",
            "recruiter_sla_days",
            filters={"tenant_id": str(current_user.tenant_id), "is_default": "true"},
            single=True,
        )
        sla_days = sla_config["recruiter_sla_days"] if sla_config else 14

    # Calculate SLA deadline
    now = datetime.now(timezone.utc)
    sla_deadline = now + timedelta(days=sla_days)

    # Create assignment
    assignment_dict = {
        "tenant_id": str(current_user.tenant_id),
        "requisition_id": str(job_id),
        "recruiter_id": str(assignment_data.recruiter_id),
        "assigned_at": now.isoformat(),
        "assigned_by": str(current_user.user_id),
        "sla_days": sla_days,
        "sla_deadline": sla_deadline.isoformat(),
        "status": "active",
        "notes": assignment_data.notes,
    }

    assignment = await client.insert("recruiter_assignments", assignment_dict)

    # Also update the job's primary_recruiter_id if not set
    if not job.get("primary_recruiter_id"):
        await client.update(
            "job_requisitions",
            {"primary_recruiter_id": str(assignment_data.recruiter_id)},
            filters={"id": str(job_id)},
        )

    return RecruiterAssignmentResponse(
        id=UUID(assignment["id"]),
        tenant_id=UUID(assignment["tenant_id"]),
        requisition_id=UUID(assignment["requisition_id"]),
        recruiter_id=UUID(assignment["recruiter_id"]),
        assigned_at=datetime.fromisoformat(assignment["assigned_at"].replace("Z", "+00:00")),
        assigned_by=UUID(assignment["assigned_by"]) if assignment.get("assigned_by") else None,
        sla_days=assignment.get("sla_days"),
        sla_deadline=datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00")) if assignment.get("sla_deadline") else None,
        status=assignment["status"],
        completed_at=None,
        reassigned_to=None,
        reassigned_at=None,
        reassignment_reason=None,
        notes=assignment.get("notes"),
        created_at=datetime.fromisoformat(assignment["created_at"].replace("Z", "+00:00")),
        updated_at=None,
        recruiter_name=recruiter.get('full_name', ''),
        recruiter_email=recruiter.get("email"),
        job_title=job.get("external_title"),
        requisition_number=job.get("requisition_number"),
    )


@router.post("/jobs/{job_id}/reassign", response_model=RecruiterAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def reassign_job(
    job_id: UUID,
    reassign_data: RecruiterReassign,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Reassign a job from the current recruiter to a new recruiter."""
    client = get_supabase_client()

    # Verify job exists
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

    # Get current active assignment
    current_assignment = await client.select(
        "recruiter_assignments",
        "*",
        filters={
            "requisition_id": str(job_id),
            "status": "active",
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not current_assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active assignment found for this job",
        )

    # Verify new recruiter exists
    new_recruiter = await client.select(
        "users",
        "id,full_name,email,tenant_id",
        filters={"id": str(reassign_data.new_recruiter_id)},
        single=True,
    )

    if not new_recruiter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New recruiter not found",
        )

    if new_recruiter["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign recruiter from different tenant",
        )

    # Mark current assignment as reassigned
    now = datetime.now(timezone.utc)
    await client.update(
        "recruiter_assignments",
        {
            "status": "reassigned",
            "reassigned_to": str(reassign_data.new_recruiter_id),
            "reassigned_at": now.isoformat(),
            "reassignment_reason": reassign_data.reassignment_reason,
            "updated_at": now.isoformat(),
        },
        filters={"id": current_assignment["id"]},
    )

    # Get SLA days (use same as previous or default)
    sla_days = current_assignment.get("sla_days") or 14
    sla_deadline = now + timedelta(days=sla_days)

    # Create new assignment
    new_assignment_dict = {
        "tenant_id": str(current_user.tenant_id),
        "requisition_id": str(job_id),
        "recruiter_id": str(reassign_data.new_recruiter_id),
        "assigned_at": now.isoformat(),
        "assigned_by": str(current_user.user_id),
        "sla_days": sla_days,
        "sla_deadline": sla_deadline.isoformat(),
        "status": "active",
        "notes": reassign_data.notes,
    }

    new_assignment = await client.insert("recruiter_assignments", new_assignment_dict)

    # Update job's primary_recruiter_id
    await client.update(
        "job_requisitions",
        {"primary_recruiter_id": str(reassign_data.new_recruiter_id)},
        filters={"id": str(job_id)},
    )

    return RecruiterAssignmentResponse(
        id=UUID(new_assignment["id"]),
        tenant_id=UUID(new_assignment["tenant_id"]),
        requisition_id=UUID(new_assignment["requisition_id"]),
        recruiter_id=UUID(new_assignment["recruiter_id"]),
        assigned_at=datetime.fromisoformat(new_assignment["assigned_at"].replace("Z", "+00:00")),
        assigned_by=UUID(new_assignment["assigned_by"]) if new_assignment.get("assigned_by") else None,
        sla_days=new_assignment.get("sla_days"),
        sla_deadline=datetime.fromisoformat(new_assignment["sla_deadline"].replace("Z", "+00:00")) if new_assignment.get("sla_deadline") else None,
        status=new_assignment["status"],
        completed_at=None,
        reassigned_to=None,
        reassigned_at=None,
        reassignment_reason=None,
        notes=new_assignment.get("notes"),
        created_at=datetime.fromisoformat(new_assignment["created_at"].replace("Z", "+00:00")),
        updated_at=None,
        recruiter_name=new_recruiter.get('full_name', ''),
        recruiter_email=new_recruiter.get("email"),
        job_title=job.get("external_title"),
        requisition_number=job.get("requisition_number"),
    )


@router.get("/my-assignments", response_model=list[MyAssignmentsResponse])
async def get_my_assignments(
    include_completed: bool = Query(False, description="Include completed/reassigned assignments"),
    current_user: TokenData = Depends(require_any_permission(Permission.JOBS_VIEW, Permission.JOBS_CREATE)),
):
    """Get current user's job assignments."""
    client = get_supabase_client()

    # Build filters
    filters = {
        "recruiter_id": str(current_user.user_id),
        "tenant_id": str(current_user.tenant_id),
    }
    if not include_completed:
        filters["status"] = "active"

    assignments = await client.select("recruiter_assignments", "*", filters=filters) or []

    # Get job details for each assignment
    result = []
    for assignment in assignments:
        job = await client.select(
            "job_requisitions",
            "id,external_title,requisition_number,status,department_id",
            filters={"id": assignment["requisition_id"]},
            single=True,
        )

        if not job:
            continue

        # Get candidate count
        applications = await client.select(
            "applications",
            "id",
            filters={"requisition_id": assignment["requisition_id"]},
        ) or []
        candidate_count = len(applications)

        # Get department name if available
        department_name = None
        if job.get("department_id"):
            dept = await client.select(
                "departments",
                "name",
                filters={"id": job["department_id"]},
                single=True,
            )
            if dept:
                department_name = dept.get("name")

        days_remaining, sla_status = calculate_sla_status(
            datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00")) if assignment.get("sla_deadline") else None
        )

        result.append(MyAssignmentsResponse(
            id=UUID(assignment["id"]),
            requisition_id=UUID(assignment["requisition_id"]),
            requisition_number=job.get("requisition_number", ""),
            job_title=job.get("external_title", ""),
            department_name=department_name,
            assigned_at=datetime.fromisoformat(assignment["assigned_at"].replace("Z", "+00:00")),
            sla_days=assignment.get("sla_days"),
            sla_deadline=datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00")) if assignment.get("sla_deadline") else None,
            status=assignment["status"],
            days_remaining=days_remaining,
            sla_status=sla_status,
            candidate_count=candidate_count,
            job_status=job.get("status"),
        ))

    # Sort by SLA deadline ascending (most urgent first)
    result.sort(key=lambda x: x.sla_deadline or datetime.max.replace(tzinfo=timezone.utc))

    return result


@router.post("/assignments/{assignment_id}/complete", response_model=RecruiterAssignmentResponse)
async def complete_assignment(
    assignment_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Mark an assignment as completed (job filled or assignment task done)."""
    client = get_supabase_client()

    # Get assignment
    assignment = await client.select(
        "recruiter_assignments",
        "*",
        filters={"id": str(assignment_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active assignments can be completed",
        )

    # Mark as completed
    now = datetime.now(timezone.utc)
    updated = await client.update(
        "recruiter_assignments",
        {
            "status": "completed",
            "completed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
        filters={"id": str(assignment_id)},
    )

    return RecruiterAssignmentResponse(
        id=UUID(updated["id"]),
        tenant_id=UUID(updated["tenant_id"]),
        requisition_id=UUID(updated["requisition_id"]),
        recruiter_id=UUID(updated["recruiter_id"]),
        assigned_at=datetime.fromisoformat(updated["assigned_at"].replace("Z", "+00:00")),
        assigned_by=UUID(updated["assigned_by"]) if updated.get("assigned_by") else None,
        sla_days=updated.get("sla_days"),
        sla_deadline=datetime.fromisoformat(updated["sla_deadline"].replace("Z", "+00:00")) if updated.get("sla_deadline") else None,
        status=updated["status"],
        completed_at=datetime.fromisoformat(updated["completed_at"].replace("Z", "+00:00")) if updated.get("completed_at") else None,
        reassigned_to=UUID(updated["reassigned_to"]) if updated.get("reassigned_to") else None,
        reassigned_at=datetime.fromisoformat(updated["reassigned_at"].replace("Z", "+00:00")) if updated.get("reassigned_at") else None,
        reassignment_reason=updated.get("reassignment_reason"),
        notes=updated.get("notes"),
        created_at=datetime.fromisoformat(updated["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(updated["updated_at"].replace("Z", "+00:00")) if updated.get("updated_at") else None,
    )


@router.get("/sla/alerts", response_model=list[SLAAlertResponse])
async def get_sla_alerts(
    include_acknowledged: bool = Query(False, description="Include acknowledged alerts"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get SLA alerts for the tenant."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}
    if entity_type:
        filters["entity_type"] = entity_type

    alerts = await client.select("sla_alerts", "*", filters=filters) or []

    # Filter acknowledged if needed
    if not include_acknowledged:
        alerts = [a for a in alerts if not a.get("acknowledged_at")]

    # Enrich alerts with entity details
    result = []
    for alert in alerts:
        entity_title = None
        entity_number = None
        recruiter_name = None

        if alert["entity_type"] == "job_opening":
            job = await client.select(
                "job_requisitions",
                "external_title,requisition_number",
                filters={"id": alert["entity_id"]},
                single=True,
            )
            if job:
                entity_title = job.get("external_title")
                entity_number = job.get("requisition_number")

        elif alert["entity_type"] == "recruiter_assignment":
            assignment = await client.select(
                "recruiter_assignments",
                "requisition_id,recruiter_id",
                filters={"id": alert["entity_id"]},
                single=True,
            )
            if assignment:
                job = await client.select(
                    "job_requisitions",
                    "external_title,requisition_number",
                    filters={"id": assignment["requisition_id"]},
                    single=True,
                )
                if job:
                    entity_title = job.get("external_title")
                    entity_number = job.get("requisition_number")

                user = await client.select(
                    "users",
                    "full_name",
                    filters={"id": assignment["recruiter_id"]},
                    single=True,
                )
                if user:
                    recruiter_name = user.get('full_name', '')

        result.append(SLAAlertResponse(
            id=UUID(alert["id"]),
            tenant_id=UUID(alert["tenant_id"]),
            alert_type=alert["alert_type"],
            entity_type=alert["entity_type"],
            entity_id=UUID(alert["entity_id"]),
            message=alert.get("message"),
            triggered_at=datetime.fromisoformat(alert["triggered_at"].replace("Z", "+00:00")),
            acknowledged_at=datetime.fromisoformat(alert["acknowledged_at"].replace("Z", "+00:00")) if alert.get("acknowledged_at") else None,
            acknowledged_by=UUID(alert["acknowledged_by"]) if alert.get("acknowledged_by") else None,
            entity_title=entity_title,
            entity_number=entity_number,
            recruiter_name=recruiter_name,
        ))

    # Sort by triggered_at descending
    result.sort(key=lambda x: x.triggered_at, reverse=True)

    return result


@router.post("/sla/alerts/{alert_id}/acknowledge", response_model=SLAAlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    request: AcknowledgeAlertRequest,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Acknowledge an SLA alert."""
    client = get_supabase_client()

    # Get alert
    alert = await client.select(
        "sla_alerts",
        "*",
        filters={"id": str(alert_id), "tenant_id": str(current_user.tenant_id)},
        single=True,
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if alert.get("acknowledged_at"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert already acknowledged",
        )

    # Update alert
    now = datetime.now(timezone.utc)
    updated = await client.update(
        "sla_alerts",
        {
            "acknowledged_at": now.isoformat(),
            "acknowledged_by": str(current_user.user_id),
        },
        filters={"id": str(alert_id)},
    )

    return SLAAlertResponse(
        id=UUID(updated["id"]),
        tenant_id=UUID(updated["tenant_id"]),
        alert_type=updated["alert_type"],
        entity_type=updated["entity_type"],
        entity_id=UUID(updated["entity_id"]),
        message=updated.get("message"),
        triggered_at=datetime.fromisoformat(updated["triggered_at"].replace("Z", "+00:00")),
        acknowledged_at=datetime.fromisoformat(updated["acknowledged_at"].replace("Z", "+00:00")) if updated.get("acknowledged_at") else None,
        acknowledged_by=UUID(updated["acknowledged_by"]) if updated.get("acknowledged_by") else None,
    )


@router.get("/sla/at-risk")
async def get_at_risk_assignments(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get summary of assignments at risk (amber/red SLA status)."""
    client = get_supabase_client()

    # Get all active assignments
    assignments = await client.select(
        "recruiter_assignments",
        "*",
        filters={"tenant_id": str(current_user.tenant_id), "status": "active"},
    ) or []

    amber_count = 0
    red_count = 0
    at_risk_jobs = []

    for assignment in assignments:
        if not assignment.get("sla_deadline"):
            continue

        days_remaining, sla_status = calculate_sla_status(
            datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00"))
        )

        if sla_status == "amber":
            amber_count += 1
            at_risk_jobs.append({
                "assignment_id": assignment["id"],
                "requisition_id": assignment["requisition_id"],
                "recruiter_id": assignment["recruiter_id"],
                "days_remaining": days_remaining,
                "sla_status": sla_status,
            })
        elif sla_status == "red":
            red_count += 1
            at_risk_jobs.append({
                "assignment_id": assignment["id"],
                "requisition_id": assignment["requisition_id"],
                "recruiter_id": assignment["recruiter_id"],
                "days_remaining": days_remaining,
                "sla_status": sla_status,
            })

    return {
        "summary": {
            "total_active": len(assignments),
            "amber": amber_count,
            "red": red_count,
            "healthy": len(assignments) - amber_count - red_count,
        },
        "at_risk": at_risk_jobs,
    }
