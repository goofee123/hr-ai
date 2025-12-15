"""Hybrid Candidate-Job Matching Service with LLM Reranking.

Implements a scalable multi-stage matching pipeline:
1. Hard Filters (SQL) - Filter by location, visa, min experience
2. Skill Tag Intersection - Pre-indexed skill matching
3. Embedding Similarity (pgvector) - Vector similarity on shortlist
4. LLM Rerank (optional) - Detailed reasoning on top candidates

This avoids O(N*LLM) cost by only calling LLM on top 20 candidates.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import httpx

from app.config import get_settings
from app.core.supabase_client import get_supabase_client
from app.recruiting.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)
settings = get_settings()

# LLM Configuration
LLM_RERANK_MODEL = "gpt-4o-mini"
LLM_RERANK_MAX_CANDIDATES = 20


@dataclass
class MatchResult:
    """Result of candidate-job matching with breakdown."""
    candidate_id: UUID
    overall_score: float  # 0.0 to 1.0
    match_breakdown: dict[str, float]  # Component scores
    reasoning: Optional[str] = None  # LLM reasoning (if reranked)
    model_name: Optional[str] = None  # Model used for reranking
    confidence_label: str = "Inferred"  # Explicit, Very Likely, Inferred, Uncertain


@dataclass
class MatchingConfig:
    """Configuration for matching weights."""
    skills_weight: float = 0.30
    experience_weight: float = 0.25
    embedding_weight: float = 0.30
    location_weight: float = 0.10
    recency_weight: float = 0.05

    # Thresholds
    min_skill_match: float = 0.3  # Min skill overlap to consider
    min_embedding_score: float = 0.5  # Min embedding similarity

    # Stage limits
    hard_filter_limit: int = 1000  # After hard filters
    skill_match_limit: int = 200  # After skill matching
    embedding_limit: int = 50  # After embedding
    llm_rerank_limit: int = 20  # Max to send to LLM


class HybridMatchingService:
    """Multi-stage hybrid matching service."""

    def __init__(self):
        self.client = get_supabase_client()
        self.embedding_service = get_embedding_service()
        self.config = MatchingConfig()
        self.openai_api_key = getattr(settings, 'openai_api_key', None)

    def _get_confidence_label(self, score: float) -> str:
        """Map score to confidence label."""
        if score >= 0.90:
            return "Explicit"
        elif score >= 0.75:
            return "Very Likely"
        elif score >= 0.60:
            return "Inferred"
        return "Uncertain"

    async def get_recommended_candidates(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        limit: int = 10,
        use_llm_rerank: bool = True,
        filters: Optional[dict] = None,
    ) -> list[MatchResult]:
        """Find best matching candidates for a job using hybrid approach.

        Pipeline:
        1. Hard filters (SQL) → ~1000 candidates
        2. Skill tag match → ~200 candidates
        3. Embedding similarity → ~50 candidates
        4. LLM rerank (optional) → top 10-20 with reasoning

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            limit: Final number of candidates to return
            use_llm_rerank: Whether to use LLM for final reranking
            filters: Additional hard filters (location, visa_required, etc.)

        Returns:
            List of MatchResult with scores and reasoning
        """
        try:
            # Get job details for matching
            job = await self._get_job_details(tenant_id, requisition_id)
            if not job:
                return []

            # Stage 1: Hard Filters
            logger.info(f"Stage 1: Applying hard filters for job {requisition_id}")
            candidates = await self._apply_hard_filters(
                tenant_id, job, filters, limit=self.config.hard_filter_limit
            )
            logger.info(f"Stage 1 result: {len(candidates)} candidates after hard filters")

            if not candidates:
                return []

            # Stage 2: Skill Tag Matching
            logger.info(f"Stage 2: Skill tag matching")
            job_skills = set(job.get("required_skills", []) or [])
            candidates_with_skills = await self._score_skill_match(
                candidates, job_skills, limit=self.config.skill_match_limit
            )
            logger.info(f"Stage 2 result: {len(candidates_with_skills)} candidates after skill match")

            if not candidates_with_skills:
                # Fall back to top candidates by other criteria
                candidates_with_skills = candidates[:self.config.skill_match_limit]

            # Stage 3: Embedding Similarity
            logger.info(f"Stage 3: Embedding similarity")
            candidates_with_embeddings = await self._score_embedding_similarity(
                tenant_id, candidates_with_skills, requisition_id,
                limit=self.config.embedding_limit
            )
            logger.info(f"Stage 3 result: {len(candidates_with_embeddings)} candidates after embedding")

            # Stage 4: LLM Reranking (optional)
            if use_llm_rerank and self.openai_api_key and len(candidates_with_embeddings) > 0:
                logger.info(f"Stage 4: LLM reranking top {min(len(candidates_with_embeddings), LLM_RERANK_MAX_CANDIDATES)} candidates")
                final_candidates = await self._llm_rerank(
                    job, candidates_with_embeddings[:LLM_RERANK_MAX_CANDIDATES],
                    limit=limit
                )
                logger.info(f"Stage 4 result: {len(final_candidates)} candidates after LLM rerank")
            else:
                # Skip LLM, use weighted combination of stage scores
                final_candidates = self._compute_final_scores(
                    candidates_with_embeddings, job, limit
                )

            return final_candidates

        except Exception as e:
            logger.error(f"Error in get_recommended_candidates: {e}")
            return []

    async def _get_job_details(self, tenant_id: UUID, requisition_id: UUID) -> Optional[dict]:
        """Get job requisition details."""
        job = await self.client.select(
            "job_requisitions",
            "*",
            filters={"id": str(requisition_id), "tenant_id": str(tenant_id)},
            single=True,
        )
        return job

    async def _apply_hard_filters(
        self,
        tenant_id: UUID,
        job: dict,
        filters: Optional[dict],
        limit: int,
    ) -> list[dict]:
        """Stage 1: Apply hard SQL filters to narrow candidate pool.

        Filters on:
        - Tenant isolation
        - Not deleted
        - (Optional) Location match
        - (Optional) Min experience
        - (Optional) Employment type preferences
        """
        base_filters = {"tenant_id": str(tenant_id)}

        # Only include non-deleted candidates
        # (soft delete uses deleted_at field)

        candidates = await self.client.select(
            "candidates",
            "id, first_name, last_name, email, skills, source, current_title, current_company, experience_years, linkedin_url, created_at",
            filters=base_filters,
            limit=limit,
        ) or []

        # Filter out soft-deleted candidates (if deleted_at exists)
        candidates = [c for c in candidates if not c.get("deleted_at")]

        # Apply additional filters
        if filters:
            if filters.get("min_experience"):
                candidates = [
                    c for c in candidates
                    if (c.get("experience_years") or 0) >= filters["min_experience"]
                ]

            if filters.get("location"):
                loc = filters["location"].lower()
                candidates = [
                    c for c in candidates
                    if loc in (c.get("location") or "").lower()
                ]

        return candidates

    async def _score_skill_match(
        self,
        candidates: list[dict],
        job_skills: set[str],
        limit: int,
    ) -> list[dict]:
        """Stage 2: Score candidates by skill overlap.

        Uses Jaccard similarity on skill sets.
        """
        if not job_skills:
            return candidates[:limit]

        job_skills_lower = {s.lower() for s in job_skills}

        scored = []
        for candidate in candidates:
            candidate_skills = candidate.get("skills") or []
            candidate_skills_lower = {s.lower() for s in candidate_skills}

            if not candidate_skills_lower:
                skill_score = 0.0
            else:
                # Jaccard similarity
                intersection = len(job_skills_lower & candidate_skills_lower)
                union = len(job_skills_lower | candidate_skills_lower)
                skill_score = intersection / union if union > 0 else 0.0

            candidate["_skill_score"] = skill_score
            scored.append(candidate)

        # Sort by skill score and filter
        scored.sort(key=lambda x: x.get("_skill_score", 0), reverse=True)

        # Keep candidates with at least some skill match, or top N if none
        matched = [c for c in scored if c.get("_skill_score", 0) >= self.config.min_skill_match]
        if not matched:
            matched = scored

        return matched[:limit]

    async def _score_embedding_similarity(
        self,
        tenant_id: UUID,
        candidates: list[dict],
        requisition_id: UUID,
        limit: int,
    ) -> list[dict]:
        """Stage 3: Score candidates by embedding similarity.

        Uses pgvector cosine similarity between candidate and job embeddings.
        """
        # Get job embedding
        job_embedding = await self.embedding_service.get_job_embedding(
            tenant_id, requisition_id
        )

        if not job_embedding or not job_embedding.get("embedding"):
            # No embedding available, skip this stage
            for candidate in candidates:
                candidate["_embedding_score"] = 0.5  # Neutral score
            return candidates[:limit]

        # Get candidate embeddings and compute similarity
        for candidate in candidates:
            candidate_embedding = await self.embedding_service.get_candidate_embedding(
                tenant_id, UUID(candidate["id"])
            )

            if candidate_embedding and candidate_embedding.get("embedding"):
                # Compute cosine similarity
                # Note: In production, this would use pgvector's <=> operator
                similarity = await self._compute_cosine_similarity(
                    candidate_embedding["embedding"],
                    job_embedding["embedding"]
                )
                candidate["_embedding_score"] = similarity
            else:
                candidate["_embedding_score"] = 0.5  # Neutral if no embedding

        # Sort by embedding score
        candidates.sort(key=lambda x: x.get("_embedding_score", 0), reverse=True)

        # Filter by minimum score
        filtered = [
            c for c in candidates
            if c.get("_embedding_score", 0) >= self.config.min_embedding_score
        ]
        if not filtered:
            filtered = candidates

        return filtered[:limit]

    async def _compute_cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return (dot_product / (norm1 * norm2) + 1) / 2  # Normalize to 0-1

    async def _llm_rerank(
        self,
        job: dict,
        candidates: list[dict],
        limit: int,
    ) -> list[MatchResult]:
        """Stage 4: Use LLM to rerank top candidates with detailed reasoning.

        This is the expensive step - only called on shortlisted candidates.
        """
        if not candidates:
            return []

        # Build prompt
        job_summary = f"""
Job Title: {job.get('external_title', job.get('title', 'Unknown'))}
Description: {job.get('job_description', 'No description')[:1000]}
Requirements: {job.get('requirements', 'Not specified')[:500]}
Required Skills: {', '.join(job.get('required_skills', []) or [])}
"""

        candidate_summaries = []
        for i, c in enumerate(candidates):
            summary = f"""
Candidate {i+1}: {c.get('first_name', '')} {c.get('last_name', '')}
- Current Role: {c.get('current_title', 'Unknown')} at {c.get('current_company', 'Unknown')}
- Experience: {c.get('experience_years', 'Unknown')} years
- Skills: {', '.join(c.get('skills', []) or [])}
- Source: {c.get('source', 'Unknown')}
"""
            candidate_summaries.append(summary)

        prompt = f"""You are evaluating candidates for a job. Rank them by fit.

{job_summary}

CANDIDATES:
{''.join(candidate_summaries)}

For each candidate, provide:
1. A score from 0.0 to 1.0 (1.0 = perfect fit)
2. A brief reasoning (1-2 sentences)

Return JSON array sorted by score descending:
[
  {{"candidate_index": 0, "score": 0.85, "reasoning": "Strong Python skills and 5+ years experience match requirements"}},
  ...
]

Only return the JSON array, no other text.
"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_RERANK_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                    timeout=60,
                )

                if response.status_code != 200:
                    logger.error(f"LLM rerank failed: {response.status_code}")
                    return self._compute_final_scores(candidates, job, limit)

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse LLM response
                rankings = json.loads(content)

                # Build results
                results = []
                for ranking in rankings[:limit]:
                    idx = ranking.get("candidate_index", 0)
                    if idx < len(candidates):
                        candidate = candidates[idx]
                        score = float(ranking.get("score", 0.5))

                        results.append(MatchResult(
                            candidate_id=UUID(candidate["id"]),
                            overall_score=score,
                            match_breakdown={
                                "skill_score": candidate.get("_skill_score", 0),
                                "embedding_score": candidate.get("_embedding_score", 0),
                                "llm_score": score,
                            },
                            reasoning=ranking.get("reasoning"),
                            model_name=LLM_RERANK_MODEL,
                            confidence_label=self._get_confidence_label(score),
                        ))

                return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._compute_final_scores(candidates, job, limit)
        except Exception as e:
            logger.error(f"LLM rerank error: {e}")
            return self._compute_final_scores(candidates, job, limit)

    def _compute_final_scores(
        self,
        candidates: list[dict],
        job: dict,
        limit: int,
    ) -> list[MatchResult]:
        """Compute final weighted scores without LLM.

        Used when LLM is disabled or unavailable.
        """
        results = []
        for candidate in candidates[:limit]:
            skill_score = candidate.get("_skill_score", 0)
            embedding_score = candidate.get("_embedding_score", 0.5)

            # Weighted combination
            overall = (
                self.config.skills_weight * skill_score +
                self.config.embedding_weight * embedding_score +
                0.5 * (1 - self.config.skills_weight - self.config.embedding_weight)  # Base score
            )

            results.append(MatchResult(
                candidate_id=UUID(candidate["id"]),
                overall_score=overall,
                match_breakdown={
                    "skill_score": skill_score,
                    "embedding_score": embedding_score,
                },
                reasoning=None,
                model_name=None,
                confidence_label=self._get_confidence_label(overall),
            ))

        # Sort by score
        results.sort(key=lambda x: x.overall_score, reverse=True)
        return results

    async def get_matching_config(self, tenant_id: UUID) -> MatchingConfig:
        """Get matching configuration for tenant.

        Admin-only - recruiters can only view, not modify.
        """
        # In future: Load from tenant settings
        return self.config

    async def update_matching_config(
        self,
        tenant_id: UUID,
        config: dict,
    ) -> MatchingConfig:
        """Update matching configuration (admin only)."""
        # Update weights
        if "skills_weight" in config:
            self.config.skills_weight = config["skills_weight"]
        if "experience_weight" in config:
            self.config.experience_weight = config["experience_weight"]
        if "embedding_weight" in config:
            self.config.embedding_weight = config["embedding_weight"]
        if "location_weight" in config:
            self.config.location_weight = config["location_weight"]
        if "recency_weight" in config:
            self.config.recency_weight = config["recency_weight"]

        # In future: Persist to database
        return self.config


# Singleton factory
_hybrid_matching_service: Optional[HybridMatchingService] = None


def get_hybrid_matching_service() -> HybridMatchingService:
    """Get or create the hybrid matching service singleton."""
    global _hybrid_matching_service
    if _hybrid_matching_service is None:
        _hybrid_matching_service = HybridMatchingService()
    return _hybrid_matching_service
