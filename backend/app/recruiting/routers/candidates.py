"""Candidates router - using Supabase REST API."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.candidate import (
    CandidateCreate,
    CandidateDetailResponse,
    CandidateResponse,
    CandidateSearchResult,
    CandidateUpdate,
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
