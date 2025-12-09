"""Candidates router - using Supabase REST API."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

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
from app.shared.schemas.common import PaginatedResponse

router = APIRouter()


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
