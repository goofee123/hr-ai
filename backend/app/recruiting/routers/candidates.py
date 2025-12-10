"""Candidates router - using Supabase REST API."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.candidate import (
    CandidateApplicationHistory,
    CandidateActivityLog,
    CandidateCreate,
    CandidateDetailResponse,
    CandidateMatchingJob,
    CandidateResponse,
    CandidateSearchResult,
    CandidateUpdate,
    ConvertToApplicantRequest,
    ResumeResponse,
)
from app.recruiting.services.candidate_deduplication import (
    CandidateDeduplicationService,
    MatchConfidence,
    candidate_deduplication_service,
)
from app.shared.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Deduplication Schemas
# ============================================================================

class DeduplicationCheckRequest(BaseModel):
    """Request to check for duplicate candidates."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    first_name: str = ""
    last_name: str = ""


class DeduplicationCheckResponse(BaseModel):
    """Response from deduplication check."""
    is_duplicate: bool
    existing_candidate_id: Optional[UUID] = None
    confidence: str  # exact, high, medium, low, none
    match_reasons: List[str]
    suggested_action: str  # create_new, update_existing, merge_required, review_required


class CandidateMergeRequest(BaseModel):
    """Request to merge candidate profiles."""
    source_candidate_id: UUID = Field(..., description="Candidate to merge FROM (will be deleted)")
    target_candidate_id: UUID = Field(..., description="Candidate to merge INTO (will be kept)")
    merge_strategy: str = Field(
        default="smart_merge",
        description="How to merge: 'prefer_new', 'prefer_existing', 'smart_merge'"
    )


class CandidateSubmitOrUpdateRequest(BaseModel):
    """Request for smart candidate submit - creates new or updates existing."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[dict] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    skills: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    force_create: bool = Field(
        default=False,
        description="Force create new candidate even if duplicate detected"
    )


@router.get("", response_model=PaginatedResponse[CandidateSearchResult])
async def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = None,
    search: Optional[str] = None,
    skills: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List candidates with filters and search."""
    client = get_supabase_client()

    # Build filters
    filters = {"tenant_id": str(current_user.tenant_id)}
    if source:
        filters["source"] = source

    # Get all candidates (we'll filter in Python for now)
    candidates = await client.select("candidates", "*", filters=filters) or []

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        candidates = [
            c for c in candidates
            if search_lower in c.get("first_name", "").lower()
            or search_lower in c.get("last_name", "").lower()
            or search_lower in c.get("email", "").lower()
        ]

    # Apply skills filter if provided
    if skills:
        candidates = [
            c for c in candidates
            if any(skill in c.get("skills", []) for skill in skills)
        ]

    # Apply tags filter if provided
    if tags:
        candidates = [
            c for c in candidates
            if any(tag in c.get("tags", []) for tag in tags)
        ]

    # Get total count before pagination
    total = len(candidates)

    # Sort by created_at descending
    candidates.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Apply pagination
    offset = (page - 1) * page_size
    candidates = candidates[offset:offset + page_size]

    return PaginatedResponse.create(
        items=[CandidateSearchResult.model_validate(c) for c in candidates],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    candidate_data: CandidateCreate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_CREATE)),
):
    """Create a new candidate."""
    client = get_supabase_client()

    # Check for duplicate email
    existing = await client.select(
        "candidates",
        "id",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "email": candidate_data.email,
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate with this email already exists",
        )

    # Create candidate
    candidate_dict = {
        "tenant_id": str(current_user.tenant_id),
        **candidate_data.model_dump(),
    }

    candidate = await client.insert("candidates", candidate_dict)

    return CandidateResponse.model_validate(candidate)


@router.get("/search")
async def search_candidates(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Quick search for candidates (for autocomplete)."""
    client = get_supabase_client()

    # Get all candidates for tenant
    candidates = await client.select(
        "candidates",
        "*",
        filters={"tenant_id": str(current_user.tenant_id)},
    ) or []

    # Filter by search term
    search_lower = q.lower()
    candidates = [
        c for c in candidates
        if search_lower in c.get("first_name", "").lower()
        or search_lower in c.get("last_name", "").lower()
        or search_lower in c.get("email", "").lower()
    ][:limit]

    return [
        {
            "id": c["id"],
            "full_name": f"{c['first_name']} {c['last_name']}",
            "email": c["email"],
        }
        for c in candidates
    ]


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get a candidate by ID with resumes."""
    client = get_supabase_client()

    candidate = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Get resumes for candidate
    resumes = await client.select(
        "resumes",
        "*",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    # Sort by version_number descending
    resumes.sort(key=lambda x: x.get("version_number", 0), reverse=True)

    candidate["resumes"] = resumes

    return CandidateDetailResponse.model_validate(candidate)


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    candidate_data: CandidateUpdate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Update a candidate."""
    client = get_supabase_client()

    # Check candidate exists
    candidate = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Check for email conflict if changing email
    if candidate_data.email and candidate_data.email != candidate["email"]:
        existing = await client.select(
            "candidates",
            "id",
            filters={
                "tenant_id": str(current_user.tenant_id),
                "email": candidate_data.email,
            },
            single=True,
        )
        if existing and existing["id"] != str(candidate_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another candidate with this email already exists",
            )

    # Apply updates
    update_data = candidate_data.model_dump(exclude_unset=True)
    if update_data:
        candidate = await client.update(
            "candidates",
            update_data,
            filters={"id": str(candidate_id)},
        )

    return CandidateResponse.model_validate(candidate)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_DELETE)),
):
    """Delete a candidate."""
    client = get_supabase_client()

    # Check candidate exists
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    await client.delete("candidates", filters={"id": str(candidate_id)})

    return None


@router.post("/{candidate_id}/resume", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    candidate_id: UUID,
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Upload a resume for a candidate."""
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Validate file type
    allowed_types = ["application/pdf", "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: PDF, DOC, DOCX",
        )

    # Read file
    content = await file.read()
    file_size = len(content)

    # Check file size (10MB limit)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB",
        )

    # Get next version number
    resumes = await client.select(
        "resumes",
        "version_number",
        filters={"candidate_id": str(candidate_id)},
    ) or []
    max_version = max([r.get("version_number", 0) for r in resumes], default=0)

    # For now, store file path (in production, upload to S3/Supabase Storage)
    file_path = f"resumes/{current_user.tenant_id}/{candidate_id}/{file.filename}"

    # Create resume record
    resume_dict = {
        "tenant_id": str(current_user.tenant_id),
        "candidate_id": str(candidate_id),
        "file_name": file.filename,
        "file_path": file_path,
        "file_size_bytes": file_size,
        "mime_type": file.content_type,
        "version_number": max_version + 1,
        "is_primary": True,
        "parsing_status": "pending",
    }

    resume = await client.insert("resumes", resume_dict)

    # TODO: Queue resume parsing job

    return ResumeResponse.model_validate(resume)


@router.get("/{candidate_id}/resumes", response_model=List[ResumeResponse])
async def list_resumes(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List all resumes for a candidate."""
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Get resumes
    resumes = await client.select(
        "resumes",
        "*",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    # Sort by version_number descending
    resumes.sort(key=lambda x: x.get("version_number", 0), reverse=True)

    return [ResumeResponse.model_validate(r) for r in resumes]


@router.get("/{candidate_id}/applications", response_model=List[CandidateApplicationHistory])
async def get_candidate_applications(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get all applications for a candidate (application history)."""
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Get applications
    applications = await client.select(
        "applications",
        "*",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    # Get job requisition details for each application
    result = []
    now = datetime.now(timezone.utc)

    for app in applications:
        job = await client.select(
            "job_requisitions",
            "id,requisition_number,external_title",
            filters={"id": app["requisition_id"]},
            single=True,
        )

        if job:
            applied_at = datetime.fromisoformat(app["applied_at"].replace("Z", "+00:00"))
            days_in_pipeline = (now - applied_at).days

            result.append(CandidateApplicationHistory(
                application_id=UUID(app["id"]),
                requisition_id=UUID(app["requisition_id"]),
                requisition_number=job.get("requisition_number", ""),
                job_title=job.get("external_title", ""),
                applied_at=applied_at,
                current_stage=app.get("current_stage", "Applied"),
                status=app.get("status", "new"),
                days_in_pipeline=days_in_pipeline,
            ))

    # Sort by applied_at descending
    result.sort(key=lambda x: x.applied_at, reverse=True)

    return result


@router.get("/{candidate_id}/matching-jobs", response_model=List[CandidateMatchingJob])
async def get_matching_jobs(
    candidate_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get open jobs that match the candidate's profile.

    Currently uses simple skills-based matching.
    Will use AI embeddings once Sprint 4 is complete.
    """
    client = get_supabase_client()

    # Get candidate with skills
    candidate = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    candidate_skills = set(s.lower() for s in (candidate.get("skills") or []))

    # Get open jobs
    jobs = await client.select(
        "job_requisitions",
        "*",
        filters={
            "tenant_id": str(current_user.tenant_id),
            "status": "open",
        },
    ) or []

    # Get candidate's existing applications to exclude those jobs
    existing_apps = await client.select(
        "applications",
        "requisition_id",
        filters={"candidate_id": str(candidate_id)},
    ) or []
    applied_job_ids = {app["requisition_id"] for app in existing_apps}

    # Score jobs based on skills match
    scored_jobs = []
    for job in jobs:
        # Skip jobs already applied to
        if job["id"] in applied_job_ids:
            continue

        # Simple skills matching (placeholder for AI matching later)
        job_requirements = job.get("requirements", "").lower()
        job_description = job.get("job_description", "").lower()

        match_reasons = []
        matching_skills = 0

        for skill in candidate_skills:
            if skill in job_requirements or skill in job_description:
                matching_skills += 1
                match_reasons.append(f"Skills: {skill}")

        # Calculate simple match score
        if candidate_skills:
            match_score = matching_skills / len(candidate_skills)
        else:
            match_score = 0.0

        # Only include jobs with some match or limit reached
        if match_score > 0 or len(scored_jobs) < limit:
            scored_jobs.append({
                "job": job,
                "score": match_score,
                "reasons": match_reasons[:5],  # Top 5 reasons
            })

    # Sort by score descending
    scored_jobs.sort(key=lambda x: x["score"], reverse=True)
    scored_jobs = scored_jobs[:limit]

    # Build response
    result = []
    for item in scored_jobs:
        job = item["job"]
        result.append(CandidateMatchingJob(
            requisition_id=UUID(job["id"]),
            requisition_number=job.get("requisition_number", ""),
            job_title=job.get("external_title", ""),
            department_name=None,  # Would need to join with departments
            location=None,  # Would need to join with locations
            match_score=round(item["score"], 2),
            match_reasons=item["reasons"] if item["reasons"] else None,
            job_status=job.get("status", "unknown"),
        ))

    return result


@router.get("/{candidate_id}/activity", response_model=List[CandidateActivityLog])
async def get_candidate_activity(
    candidate_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get activity timeline for a candidate."""
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "id,first_name,last_name,created_at",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    activities = []

    # Activity: Candidate created
    activities.append(CandidateActivityLog(
        id=uuid4(),
        activity_type="candidate_created",
        activity_description=f"Candidate profile created for {candidate['first_name']} {candidate['last_name']}",
        activity_data=None,
        performed_by=None,
        occurred_at=datetime.fromisoformat(candidate["created_at"].replace("Z", "+00:00")),
    ))

    # Get applications and their history
    applications = await client.select(
        "applications",
        "*",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    for app in applications:
        job = await client.select(
            "job_requisitions",
            "external_title,requisition_number",
            filters={"id": app["requisition_id"]},
            single=True,
        )
        job_title = job.get("external_title", "Unknown") if job else "Unknown"

        # Activity: Application submitted
        activities.append(CandidateActivityLog(
            id=UUID(app["id"]),
            activity_type="application_submitted",
            activity_description=f"Applied for {job_title}",
            activity_data={"requisition_id": app["requisition_id"], "stage": app.get("current_stage")},
            performed_by=None,
            occurred_at=datetime.fromisoformat(app["applied_at"].replace("Z", "+00:00")),
        ))

    # Get resumes
    resumes = await client.select(
        "resumes",
        "*",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    for resume in resumes:
        activities.append(CandidateActivityLog(
            id=UUID(resume["id"]),
            activity_type="resume_uploaded",
            activity_description=f"Resume uploaded: {resume.get('file_name', 'Unknown')}",
            activity_data={"version": resume.get("version_number")},
            performed_by=None,
            occurred_at=datetime.fromisoformat(resume["uploaded_at"].replace("Z", "+00:00")),
        ))

    # Sort by occurred_at descending
    activities.sort(key=lambda x: x.occurred_at, reverse=True)

    return activities[:limit]


@router.post("/{candidate_id}/convert-to-applicant", status_code=status.HTTP_201_CREATED)
async def convert_to_applicant(
    candidate_id: UUID,
    request: ConvertToApplicantRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_CREATE)),
):
    """Convert a candidate to an applicant for a specific job requisition.

    Creates an application record linking the candidate to the job.
    """
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Verify job requisition exists and is open
    job = await client.select(
        "job_requisitions",
        "*",
        filters={
            "id": str(request.requisition_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job requisition not found",
        )

    if job.get("status") != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job requisition is not open for applications",
        )

    # Check for existing application
    existing = await client.select(
        "applications",
        "id",
        filters={
            "candidate_id": str(candidate_id),
            "requisition_id": str(request.requisition_id),
        },
        single=True,
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate already has an application for this job",
        )

    # Get initial pipeline stage
    stages = await client.select(
        "pipeline_stages",
        "*",
        filters={"requisition_id": str(request.requisition_id)},
    ) or []

    stages.sort(key=lambda x: x.get("sort_order", 0))
    initial_stage = stages[0] if stages else None
    initial_stage_name = initial_stage["name"] if initial_stage else "Applied"
    initial_stage_id = initial_stage["id"] if initial_stage else None

    # Create application
    # Note: applications table has source_id (UUID FK) not source (string)
    # We store the source info in metadata for now, as we don't have source lookup here
    now = datetime.now(timezone.utc)
    application_dict = {
        "tenant_id": str(current_user.tenant_id),
        "candidate_id": str(candidate_id),
        "requisition_id": str(request.requisition_id),
        "applied_at": now.isoformat(),
        "current_stage": initial_stage_name,
        "current_stage_id": str(initial_stage_id) if initial_stage_id else None,
        "stage_entered_at": now.isoformat(),
        "status": "new",
        "metadata": {
            "source_text": request.source or candidate.get("source") or "sourced",
            "conversion_notes": request.notes,
            "converted_from_candidate": True,
        },
        "last_activity_at": now.isoformat(),
    }

    application = await client.insert("applications", application_dict)

    # Update candidate's total_applications count
    current_count = candidate.get("total_applications", 0)
    await client.update(
        "candidates",
        {"total_applications": current_count + 1},
        filters={"id": str(candidate_id)},
    )

    return {
        "message": "Candidate converted to applicant successfully",
        "application_id": application["id"],
        "requisition_id": str(request.requisition_id),
        "job_title": job.get("external_title"),
        "initial_stage": initial_stage_name,
    }


# ============================================================================
# Deduplication Endpoints
# ============================================================================

@router.post("/check-duplicate", response_model=DeduplicationCheckResponse)
async def check_duplicate_candidate(
    request: DeduplicationCheckRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Check if a candidate already exists based on email, phone, or LinkedIn.

    Use this endpoint before creating a candidate to detect duplicates.
    Returns match confidence and suggested action.
    """
    result = await candidate_deduplication_service.find_duplicates(
        tenant_id=current_user.tenant_id,
        email=request.email,
        phone=request.phone,
        linkedin_url=request.linkedin_url,
        first_name=request.first_name,
        last_name=request.last_name,
    )

    return DeduplicationCheckResponse(
        is_duplicate=result.is_duplicate,
        existing_candidate_id=result.existing_candidate_id,
        confidence=result.confidence.value,
        match_reasons=result.match_reasons,
        suggested_action=result.suggested_action,
    )


@router.post("/submit-or-update")
async def submit_or_update_candidate(
    request: CandidateSubmitOrUpdateRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_CREATE)),
):
    """Smart candidate submission - creates new or updates existing.

    This endpoint handles the common scenario where a candidate resubmits:
    1. Checks for existing candidate by email/phone/LinkedIn
    2. If exact match (same email), updates existing profile
    3. If high confidence match, updates existing profile
    4. If medium/low confidence, returns for review (unless force_create=True)
    5. If no match, creates new candidate

    Use this for public application forms and bulk imports.
    """
    client = get_supabase_client()

    # Check for duplicates
    dedup_result = await candidate_deduplication_service.find_duplicates(
        tenant_id=current_user.tenant_id,
        email=request.email,
        phone=request.phone,
        linkedin_url=request.linkedin_url,
        first_name=request.first_name,
        last_name=request.last_name,
    )

    candidate_data = request.model_dump(exclude={"force_create"})

    # Case 1: No duplicate found - create new
    if not dedup_result.is_duplicate:
        candidate_dict = {
            "tenant_id": str(current_user.tenant_id),
            **candidate_data,
        }
        candidate = await client.insert("candidates", candidate_dict)

        logger.info(f"Created new candidate {candidate['id']} - no duplicate found")

        return {
            "action": "created",
            "candidate_id": candidate["id"],
            "message": "New candidate created",
        }

    # Case 2: Exact or high confidence match - update existing
    if dedup_result.confidence in [MatchConfidence.EXACT, MatchConfidence.HIGH]:
        merge_result = await candidate_deduplication_service.merge_candidate_profiles(
            tenant_id=current_user.tenant_id,
            existing_candidate_id=dedup_result.existing_candidate_id,
            new_candidate_data=candidate_data,
            merge_strategy="smart_merge",
        )

        logger.info(
            f"Updated existing candidate {dedup_result.existing_candidate_id} - "
            f"confidence: {dedup_result.confidence.value}"
        )

        return {
            "action": "updated",
            "candidate_id": str(dedup_result.existing_candidate_id),
            "message": f"Existing candidate updated (match confidence: {dedup_result.confidence.value})",
            "match_reasons": dedup_result.match_reasons,
        }

    # Case 3: Medium/low confidence match - require review or force create
    if request.force_create:
        candidate_dict = {
            "tenant_id": str(current_user.tenant_id),
            **candidate_data,
        }
        candidate = await client.insert("candidates", candidate_dict)

        logger.info(
            f"Force created new candidate {candidate['id']} despite potential duplicate "
            f"{dedup_result.existing_candidate_id}"
        )

        return {
            "action": "force_created",
            "candidate_id": candidate["id"],
            "message": "New candidate created (potential duplicate ignored)",
            "potential_duplicate_id": str(dedup_result.existing_candidate_id),
            "match_confidence": dedup_result.confidence.value,
            "match_reasons": dedup_result.match_reasons,
        }

    # Return for review
    return {
        "action": "review_required",
        "candidate_id": None,
        "potential_duplicate_id": str(dedup_result.existing_candidate_id),
        "message": "Potential duplicate detected - review required",
        "match_confidence": dedup_result.confidence.value,
        "match_reasons": dedup_result.match_reasons,
        "suggested_action": dedup_result.suggested_action,
    }


@router.get("/duplicates")
async def list_potential_duplicates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List potential duplicate candidate pairs for manual review.

    Returns pairs of candidates that might be duplicates based on:
    - Same phone number
    - Same name
    - Same LinkedIn profile
    - High skill overlap

    Use this for data cleanup and deduplication maintenance.
    """
    result = await candidate_deduplication_service.get_duplicate_candidates_for_review(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
    )

    return result


@router.post("/merge")
async def merge_candidates(
    request: CandidateMergeRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Merge two candidate profiles into one.

    Merges source_candidate into target_candidate:
    - Source candidate data is merged into target
    - Source candidate's applications are transferred to target
    - Source candidate's resumes are transferred to target
    - Source candidate is then deleted

    This is a destructive operation - use with caution.
    """
    client = get_supabase_client()

    # Verify both candidates exist
    source = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(request.source_candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    target = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(request.target_candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source candidate {request.source_candidate_id} not found",
        )

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target candidate {request.target_candidate_id} not found",
        )

    # Merge profiles
    merge_result = await candidate_deduplication_service.merge_candidate_profiles(
        tenant_id=current_user.tenant_id,
        existing_candidate_id=request.target_candidate_id,
        new_candidate_data=source,
        merge_strategy=request.merge_strategy,
    )

    # Transfer applications from source to target
    source_apps = await client.select(
        "applications",
        "id",
        filters={"candidate_id": str(request.source_candidate_id)},
    ) or []

    apps_transferred = 0
    for app in source_apps:
        await client.update(
            "applications",
            {"candidate_id": str(request.target_candidate_id)},
            filters={"id": app["id"]},
        )
        apps_transferred += 1

    # Transfer resumes from source to target
    source_resumes = await client.select(
        "resumes",
        "id,version_number",
        filters={"candidate_id": str(request.source_candidate_id)},
    ) or []

    # Get max version on target
    target_resumes = await client.select(
        "resumes",
        "version_number",
        filters={"candidate_id": str(request.target_candidate_id)},
    ) or []
    max_version = max([r.get("version_number", 0) for r in target_resumes], default=0)

    resumes_transferred = 0
    for resume in source_resumes:
        max_version += 1
        await client.update(
            "resumes",
            {
                "candidate_id": str(request.target_candidate_id),
                "version_number": max_version,
                "is_primary": False,  # Don't override target's primary resume
            },
            filters={"id": resume["id"]},
        )
        resumes_transferred += 1

    # Update target's total_applications count
    new_total = target.get("total_applications", 0) + apps_transferred
    await client.update(
        "candidates",
        {"total_applications": new_total},
        filters={"id": str(request.target_candidate_id)},
    )

    # Delete source candidate
    await client.delete("candidates", filters={"id": str(request.source_candidate_id)})

    logger.info(
        f"Merged candidate {request.source_candidate_id} into {request.target_candidate_id}. "
        f"Transferred {apps_transferred} applications, {resumes_transferred} resumes."
    )

    return {
        "message": "Candidates merged successfully",
        "target_candidate_id": str(request.target_candidate_id),
        "source_candidate_id": str(request.source_candidate_id),
        "applications_transferred": apps_transferred,
        "resumes_transferred": resumes_transferred,
        "merge_strategy": request.merge_strategy,
    }


@router.get("/{candidate_id}/history")
async def get_candidate_profile_history(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get the history of a candidate's profile updates.

    Shows all resume versions and when profile data was updated.
    Useful for seeing how a candidate's profile evolved over time.
    """
    client = get_supabase_client()

    # Verify candidate exists
    candidate = await client.select(
        "candidates",
        "*",
        filters={
            "id": str(candidate_id),
            "tenant_id": str(current_user.tenant_id),
        },
        single=True,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Get all resumes (sorted by version)
    resumes = await client.select(
        "resumes",
        "id,file_name,version_number,is_primary,parsing_status,parsed_data,uploaded_at",
        filters={"candidate_id": str(candidate_id)},
    ) or []

    resumes.sort(key=lambda x: x.get("version_number", 0))

    # Build history timeline
    history = []

    # Add candidate creation
    history.append({
        "event_type": "profile_created",
        "occurred_at": candidate.get("created_at"),
        "details": {
            "name": f"{candidate.get('first_name')} {candidate.get('last_name')}",
            "email": candidate.get("email"),
            "source": candidate.get("source"),
        },
    })

    # Add resume uploads
    for resume in resumes:
        parsed_data = resume.get("parsed_data", {})
        history.append({
            "event_type": "resume_uploaded",
            "occurred_at": resume.get("uploaded_at"),
            "details": {
                "file_name": resume.get("file_name"),
                "version": resume.get("version_number"),
                "is_current_primary": resume.get("is_primary"),
                "parsing_status": resume.get("parsing_status"),
                "extracted_title": parsed_data.get("experience", [{}])[0].get("title") if parsed_data.get("experience") else None,
                "extracted_company": parsed_data.get("experience", [{}])[0].get("company") if parsed_data.get("experience") else None,
                "skills_count": len(parsed_data.get("skills", [])) if isinstance(parsed_data.get("skills"), list) else 0,
            },
        })

    # Add profile update if updated_at differs from created_at
    if candidate.get("updated_at") and candidate.get("updated_at") != candidate.get("created_at"):
        history.append({
            "event_type": "profile_updated",
            "occurred_at": candidate.get("updated_at"),
            "details": {
                "note": "Profile data was updated",
            },
        })

    # Sort by date
    history.sort(key=lambda x: x.get("occurred_at", ""), reverse=True)

    return {
        "candidate_id": str(candidate_id),
        "current_profile": {
            "name": f"{candidate.get('first_name')} {candidate.get('last_name')}",
            "email": candidate.get("email"),
            "phone": candidate.get("phone"),
            "skills": candidate.get("skills"),
            "total_applications": candidate.get("total_applications"),
            "resume_versions": len(resumes),
        },
        "history": history,
    }
