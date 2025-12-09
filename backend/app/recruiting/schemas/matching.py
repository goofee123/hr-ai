"""AI Matching schemas for candidate-job similarity."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MatchScoreBreakdown(BaseModel):
    """Breakdown of how a match score was calculated."""

    embedding_similarity: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Cosine similarity between embeddings",
    )
    skills_match: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Skills overlap score",
    )
    experience_match: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Experience level match",
    )
    location_match: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Location preference match",
    )


class CandidateMatchResponse(BaseModel):
    """Response for a candidate match to a job."""

    candidate_id: UUID
    match_score: float = Field(ge=0.0, le=1.0)
    match_breakdown: Optional[MatchScoreBreakdown] = None
    is_recommended: bool = False
    candidate: Optional[dict] = Field(
        None,
        description="Embedded candidate details",
    )


class JobMatchResponse(BaseModel):
    """Response for a job match to a candidate."""

    requisition_id: UUID
    match_score: float = Field(ge=0.0, le=1.0)
    match_breakdown: Optional[MatchScoreBreakdown] = None
    is_recommended: bool = False
    job: Optional[dict] = Field(
        None,
        description="Embedded job details",
    )


class MatchingCandidatesResponse(BaseModel):
    """Response for matching candidates endpoint."""

    requisition_id: UUID
    matches: list[CandidateMatchResponse]
    total_count: int


class MatchingJobsResponse(BaseModel):
    """Response for matching jobs endpoint."""

    candidate_id: UUID
    matches: list[JobMatchResponse]
    total_count: int


class ComputeMatchRequest(BaseModel):
    """Request to compute a specific match score."""

    candidate_id: UUID
    requisition_id: UUID
    store_result: bool = Field(
        True,
        description="Whether to store the computed result",
    )


class ComputeMatchResponse(BaseModel):
    """Response after computing a match score."""

    candidate_id: UUID
    requisition_id: UUID
    match_score: float = Field(ge=0.0, le=1.0)
    match_breakdown: Optional[MatchScoreBreakdown] = None
    is_recommended: bool = False
    error: Optional[str] = None


class BatchComputeMatchRequest(BaseModel):
    """Request to batch compute matches for a job."""

    requisition_id: UUID
    candidate_ids: Optional[list[UUID]] = Field(
        None,
        description="Specific candidates to match (None = all with embeddings)",
    )


class BatchComputeMatchResponse(BaseModel):
    """Response for batch match computation."""

    computed: int
    errors: int
    total: int
    requisition_id: UUID


class GenerateEmbeddingRequest(BaseModel):
    """Request to generate embedding for text."""

    text: str = Field(..., min_length=10, max_length=10000)
    embedding_type: str = Field(
        "custom",
        description="Type identifier for the embedding",
    )


class GenerateEmbeddingResponse(BaseModel):
    """Response after generating an embedding."""

    success: bool
    embedding_dimensions: Optional[int] = None
    error: Optional[str] = None


class CandidateEmbeddingRequest(BaseModel):
    """Request to generate and store candidate embedding."""

    candidate_id: UUID
    source_text: Optional[str] = Field(
        None,
        description="Text to embed (if not provided, uses resume text)",
    )
    embedding_type: str = Field(
        "resume_full",
        description="Type of embedding (resume_full, skills, experience)",
    )


class JobEmbeddingRequest(BaseModel):
    """Request to generate and store job embedding."""

    requisition_id: UUID
    source_text: Optional[str] = Field(
        None,
        description="Text to embed (if not provided, uses job description)",
    )
    embedding_type: str = Field(
        "description",
        description="Type of embedding (description, requirements)",
    )


class EmbeddingStatusResponse(BaseModel):
    """Status of embeddings for an entity."""

    entity_id: UUID
    entity_type: str  # 'candidate' or 'job'
    has_embedding: bool
    embedding_types: list[str] = []
    last_updated: Optional[datetime] = None
