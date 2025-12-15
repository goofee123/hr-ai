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


# =============================================================================
# HYBRID MATCHING SCHEMAS (Sprint R4 - Multi-stage pipeline with LLM rerank)
# =============================================================================

class HybridMatchFilters(BaseModel):
    """Filters for hybrid matching."""

    min_experience: Optional[int] = Field(
        None,
        ge=0,
        description="Minimum years of experience",
    )
    location: Optional[str] = Field(
        None,
        description="Location filter (partial match)",
    )
    required_skills: Optional[list[str]] = Field(
        None,
        description="Required skills to filter by",
    )


class HybridMatchResult(BaseModel):
    """Result from hybrid matching pipeline with LLM reasoning."""

    candidate_id: UUID
    overall_score: float = Field(ge=0.0, le=1.0)
    match_breakdown: dict = Field(
        default_factory=dict,
        description="Component scores (skill_score, embedding_score, llm_score)",
    )
    reasoning: Optional[str] = Field(
        None,
        description="LLM reasoning explaining the match (if LLM rerank was used)",
    )
    model_name: Optional[str] = Field(
        None,
        description="LLM model used for reranking (e.g., 'gpt-4o-mini')",
    )
    confidence_label: str = Field(
        "Inferred",
        description="Human-readable confidence: Explicit, Very Likely, Inferred, Uncertain",
    )
    candidate: Optional[dict] = Field(
        None,
        description="Embedded candidate details",
    )


class HybridMatchingRequest(BaseModel):
    """Request for hybrid matching endpoint."""

    requisition_id: UUID
    limit: int = Field(10, ge=1, le=50)
    use_llm_rerank: bool = Field(
        True,
        description="Whether to use LLM for final reranking (more accurate but slower)",
    )
    filters: Optional[HybridMatchFilters] = None


class HybridMatchingResponse(BaseModel):
    """Response from hybrid matching endpoint."""

    requisition_id: UUID
    matches: list[HybridMatchResult]
    total_candidates_scanned: int
    pipeline_stages: dict = Field(
        default_factory=dict,
        description="Count at each stage: hard_filter, skill_match, embedding, llm_rerank",
    )
    llm_model_used: Optional[str] = None


class MatchingConfigResponse(BaseModel):
    """Matching configuration (admin-viewable)."""

    skills_weight: float = Field(ge=0.0, le=1.0)
    experience_weight: float = Field(ge=0.0, le=1.0)
    embedding_weight: float = Field(ge=0.0, le=1.0)
    location_weight: float = Field(ge=0.0, le=1.0)
    recency_weight: float = Field(ge=0.0, le=1.0)
    min_skill_match: float = Field(ge=0.0, le=1.0)
    min_embedding_score: float = Field(ge=0.0, le=1.0)
    hard_filter_limit: int
    skill_match_limit: int
    embedding_limit: int
    llm_rerank_limit: int


class UpdateMatchingConfigRequest(BaseModel):
    """Request to update matching configuration (admin only)."""

    skills_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    experience_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    embedding_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    location_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    recency_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
