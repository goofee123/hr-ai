"""AI Matching router for candidate-job similarity search."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.services.matching_service import get_matching_service
from app.recruiting.services.embedding_service import get_embedding_service
from app.recruiting.schemas.matching import (
    MatchingCandidatesResponse,
    MatchingJobsResponse,
    CandidateMatchResponse,
    JobMatchResponse,
    ComputeMatchRequest,
    ComputeMatchResponse,
    BatchComputeMatchRequest,
    BatchComputeMatchResponse,
    CandidateEmbeddingRequest,
    JobEmbeddingRequest,
    EmbeddingStatusResponse,
)


router = APIRouter()


@router.get(
    "/jobs/{requisition_id}/matching-candidates",
    response_model=MatchingCandidatesResponse,
    summary="Find candidates matching a job",
)
async def get_matching_candidates(
    requisition_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Find candidates that best match a job requisition using AI similarity."""
    matching_service = get_matching_service()

    matches = await matching_service.find_matching_candidates(
        tenant_id=current_user.tenant_id,
        requisition_id=requisition_id,
        limit=limit,
        min_score=min_score,
    )

    return MatchingCandidatesResponse(
        requisition_id=requisition_id,
        matches=[
            CandidateMatchResponse(
                candidate_id=UUID(m["candidate_id"]) if isinstance(m["candidate_id"], str) else m["candidate_id"],
                match_score=m["match_score"],
                match_breakdown=m.get("match_breakdown"),
                is_recommended=m.get("is_recommended", False),
                candidate=m.get("candidate"),
            )
            for m in matches
        ],
        total_count=len(matches),
    )


@router.get(
    "/candidates/{candidate_id}/matching-jobs",
    response_model=MatchingJobsResponse,
    summary="Find jobs matching a candidate",
)
async def get_matching_jobs(
    candidate_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Find jobs that best match a candidate's profile using AI similarity."""
    matching_service = get_matching_service()

    matches = await matching_service.find_matching_jobs(
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
        limit=limit,
        min_score=min_score,
    )

    return MatchingJobsResponse(
        candidate_id=candidate_id,
        matches=[
            JobMatchResponse(
                requisition_id=UUID(m["requisition_id"]) if isinstance(m["requisition_id"], str) else m["requisition_id"],
                match_score=m["match_score"],
                match_breakdown=m.get("match_breakdown"),
                is_recommended=m.get("is_recommended", False),
                job=m.get("job"),
            )
            for m in matches
        ],
        total_count=len(matches),
    )


@router.post(
    "/compute-match",
    response_model=ComputeMatchResponse,
    summary="Compute match score",
)
async def compute_match(
    request: ComputeMatchRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Compute the match score between a specific candidate and job."""
    matching_service = get_matching_service()

    result = await matching_service.compute_match_score(
        tenant_id=current_user.tenant_id,
        candidate_id=request.candidate_id,
        requisition_id=request.requisition_id,
        store_result=request.store_result,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute match score",
        )

    return ComputeMatchResponse(
        candidate_id=request.candidate_id,
        requisition_id=request.requisition_id,
        match_score=result.get("match_score", 0.0),
        match_breakdown=result.get("match_breakdown"),
        is_recommended=result.get("is_recommended", False),
        error=result.get("error"),
    )


@router.post(
    "/batch-compute",
    response_model=BatchComputeMatchResponse,
    summary="Batch compute matches",
)
async def batch_compute_matches(
    request: BatchComputeMatchRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Batch compute match scores for multiple candidates against a job."""
    matching_service = get_matching_service()

    result = await matching_service.batch_compute_matches(
        tenant_id=current_user.tenant_id,
        requisition_id=request.requisition_id,
        candidate_ids=request.candidate_ids,
    )

    return BatchComputeMatchResponse(
        computed=result.get("computed", 0),
        errors=result.get("errors", 0),
        total=result.get("total", 0),
        requisition_id=request.requisition_id,
    )


@router.get(
    "/jobs/{requisition_id}/recommended",
    summary="Get recommended candidates",
)
async def get_recommended_candidates(
    requisition_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get candidates that have been marked as recommended for a job."""
    matching_service = get_matching_service()

    recommended = await matching_service.get_recommended_candidates(
        tenant_id=current_user.tenant_id,
        requisition_id=requisition_id,
        limit=limit,
    )

    return {
        "requisition_id": str(requisition_id),
        "recommended": recommended,
        "count": len(recommended),
    }


@router.post(
    "/embeddings/candidate",
    response_model=EmbeddingStatusResponse,
    summary="Generate candidate embedding",
)
async def generate_candidate_embedding(
    request: CandidateEmbeddingRequest,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Generate and store an embedding for a candidate's profile."""
    embedding_service = get_embedding_service()

    # If no source text provided, we'd need to fetch from resume
    # For now, require source_text
    if not request.source_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_text is required (resume text extraction not yet integrated)",
        )

    # Generate embedding
    embedding = await embedding_service.generate_embedding(request.source_text)

    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding (OpenAI API key may not be configured)",
        )

    # Store embedding
    result = await embedding_service.store_candidate_embedding(
        tenant_id=current_user.tenant_id,
        candidate_id=request.candidate_id,
        resume_id=None,
        embedding=embedding,
        embedding_type=request.embedding_type,
        source_text=request.source_text,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store embedding",
        )

    return EmbeddingStatusResponse(
        entity_id=request.candidate_id,
        entity_type="candidate",
        has_embedding=True,
        embedding_types=[request.embedding_type],
        last_updated=result.get("created_at"),
    )


@router.post(
    "/embeddings/job",
    response_model=EmbeddingStatusResponse,
    summary="Generate job embedding",
)
async def generate_job_embedding(
    request: JobEmbeddingRequest,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Generate and store an embedding for a job requisition."""
    embedding_service = get_embedding_service()

    if not request.source_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_text is required",
        )

    # Generate embedding
    embedding = await embedding_service.generate_embedding(request.source_text)

    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding (OpenAI API key may not be configured)",
        )

    # Store embedding
    result = await embedding_service.store_job_embedding(
        tenant_id=current_user.tenant_id,
        requisition_id=request.requisition_id,
        embedding=embedding,
        embedding_type=request.embedding_type,
        source_text=request.source_text,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store embedding",
        )

    return EmbeddingStatusResponse(
        entity_id=request.requisition_id,
        entity_type="job",
        has_embedding=True,
        embedding_types=[request.embedding_type],
        last_updated=result.get("created_at"),
    )


@router.get(
    "/embeddings/candidate/{candidate_id}/status",
    response_model=EmbeddingStatusResponse,
    summary="Get candidate embedding status",
)
async def get_candidate_embedding_status(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Check if a candidate has embeddings stored."""
    embedding_service = get_embedding_service()

    # Check for different embedding types
    embedding_types = []
    last_updated = None

    for emb_type in ["resume_full", "skills", "experience"]:
        emb = await embedding_service.get_candidate_embedding(
            current_user.tenant_id, candidate_id, emb_type
        )
        if emb:
            embedding_types.append(emb_type)
            if emb.get("created_at"):
                last_updated = emb["created_at"]

    return EmbeddingStatusResponse(
        entity_id=candidate_id,
        entity_type="candidate",
        has_embedding=len(embedding_types) > 0,
        embedding_types=embedding_types,
        last_updated=last_updated,
    )


@router.get(
    "/embeddings/job/{requisition_id}/status",
    response_model=EmbeddingStatusResponse,
    summary="Get job embedding status",
)
async def get_job_embedding_status(
    requisition_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Check if a job has embeddings stored."""
    embedding_service = get_embedding_service()

    # Check for different embedding types
    embedding_types = []
    last_updated = None

    for emb_type in ["description", "requirements"]:
        emb = await embedding_service.get_job_embedding(
            current_user.tenant_id, requisition_id, emb_type
        )
        if emb:
            embedding_types.append(emb_type)
            if emb.get("created_at"):
                last_updated = emb["created_at"]

    return EmbeddingStatusResponse(
        entity_id=requisition_id,
        entity_type="job",
        has_embedding=len(embedding_types) > 0,
        embedding_types=embedding_types,
        last_updated=last_updated,
    )


@router.delete(
    "/embeddings/candidate/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete candidate embeddings",
)
async def delete_candidate_embeddings(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Delete all embeddings for a candidate."""
    embedding_service = get_embedding_service()

    success = await embedding_service.delete_candidate_embeddings(
        current_user.tenant_id, candidate_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete embeddings",
        )
