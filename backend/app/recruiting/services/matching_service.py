"""Candidate-Job matching service using pgvector similarity search."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx

from app.config import get_settings
from app.recruiting.services.embedding_service import get_embedding_service


settings = get_settings()


class MatchingService:
    """Service for matching candidates to jobs using vector similarity."""

    def __init__(self):
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_role_key
        self.embedding_service = get_embedding_service()

    def _get_headers(self) -> dict:
        """Get headers for Supabase REST API calls."""
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def find_matching_candidates(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        limit: int = 20,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Find candidates that best match a job requisition.

        Uses pgvector cosine similarity to find candidates with similar embeddings.

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            limit: Maximum number of candidates to return
            min_score: Minimum match score (0.0 to 1.0)

        Returns:
            List of candidate matches with scores
        """
        try:
            # Get job embedding
            job_embedding = await self.embedding_service.get_job_embedding(
                tenant_id, requisition_id
            )

            if not job_embedding or not job_embedding.get("embedding"):
                return []

            # Use Supabase RPC function for vector similarity search
            # This requires a Supabase function to be created
            async with httpx.AsyncClient() as client:
                # Call the similarity search RPC function
                response = await client.post(
                    f"{self.supabase_url}/rest/v1/rpc/match_candidates_to_job",
                    headers=self._get_headers(),
                    json={
                        "p_tenant_id": str(tenant_id),
                        "p_requisition_id": str(requisition_id),
                        "p_match_limit": limit,
                        "p_min_score": min_score,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    return response.json()

                # If RPC doesn't exist, fall back to manual matching
                if response.status_code == 404:
                    return await self._fallback_candidate_matching(
                        tenant_id, requisition_id, limit, min_score
                    )

                print(f"Error matching candidates: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"Error in find_matching_candidates: {e}")
            return []

    async def _fallback_candidate_matching(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        limit: int,
        min_score: float,
    ) -> list[dict]:
        """Fallback matching when pgvector RPC is not available.

        This performs a simple text-based matching using stored scores
        in candidate_matches table, or returns empty if no matches exist.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Check for pre-computed matches
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/candidate_matches",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "requisition_id": f"eq.{requisition_id}",
                        "match_score": f"gte.{min_score}",
                        "order": "match_score.desc",
                        "limit": str(limit),
                        "select": "*,candidates(id,email,phone,source,skills_extracted,experience_years,current_company,current_title)",
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    matches = response.json()
                    return [
                        {
                            "candidate_id": m.get("candidate_id"),
                            "match_score": float(m.get("match_score", 0)),
                            "match_breakdown": m.get("match_breakdown", {}),
                            "is_recommended": m.get("is_recommended", False),
                            "candidate": m.get("candidates"),
                        }
                        for m in matches
                    ]

                return []

        except Exception as e:
            print(f"Error in fallback matching: {e}")
            return []

    async def find_matching_jobs(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Find jobs that best match a candidate's profile.

        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            limit: Maximum number of jobs to return
            min_score: Minimum match score

        Returns:
            List of job matches with scores
        """
        try:
            async with httpx.AsyncClient() as client:
                # Try RPC first
                response = await client.post(
                    f"{self.supabase_url}/rest/v1/rpc/match_jobs_to_candidate",
                    headers=self._get_headers(),
                    json={
                        "p_tenant_id": str(tenant_id),
                        "p_candidate_id": str(candidate_id),
                        "p_match_limit": limit,
                        "p_min_score": min_score,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    return response.json()

                # Fallback to pre-computed matches
                if response.status_code == 404:
                    return await self._fallback_job_matching(
                        tenant_id, candidate_id, limit, min_score
                    )

                return []

        except Exception as e:
            print(f"Error in find_matching_jobs: {e}")
            return []

    async def _fallback_job_matching(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        limit: int,
        min_score: float,
    ) -> list[dict]:
        """Fallback job matching using pre-computed scores."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/candidate_matches",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "candidate_id": f"eq.{candidate_id}",
                        "match_score": f"gte.{min_score}",
                        "order": "match_score.desc",
                        "limit": str(limit),
                        "select": "*,job_requisitions(id,title,department,location,status,employment_type)",
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    matches = response.json()
                    return [
                        {
                            "requisition_id": m.get("requisition_id"),
                            "match_score": float(m.get("match_score", 0)),
                            "match_breakdown": m.get("match_breakdown", {}),
                            "is_recommended": m.get("is_recommended", False),
                            "job": m.get("job_requisitions"),
                        }
                        for m in matches
                    ]

                return []

        except Exception as e:
            print(f"Error in fallback job matching: {e}")
            return []

    async def compute_match_score(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        requisition_id: UUID,
        store_result: bool = True,
    ) -> Optional[dict]:
        """Compute and optionally store match score between a candidate and job.

        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            requisition_id: Job requisition ID
            store_result: Whether to store the computed score

        Returns:
            Match score result with breakdown
        """
        try:
            # Get both embeddings
            candidate_emb = await self.embedding_service.get_candidate_embedding(
                tenant_id, candidate_id
            )
            job_emb = await self.embedding_service.get_job_embedding(
                tenant_id, requisition_id
            )

            # If either embedding is missing, we can't compute similarity
            if not candidate_emb or not job_emb:
                return {
                    "match_score": 0.0,
                    "error": "Missing embeddings for candidate or job",
                    "has_candidate_embedding": candidate_emb is not None,
                    "has_job_embedding": job_emb is not None,
                }

            # Try to compute similarity via RPC
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.supabase_url}/rest/v1/rpc/compute_similarity",
                    headers=self._get_headers(),
                    json={
                        "p_candidate_id": str(candidate_id),
                        "p_requisition_id": str(requisition_id),
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    result = response.json()
                    score = result if isinstance(result, (int, float)) else result.get("score", 0)

                    match_result = {
                        "candidate_id": str(candidate_id),
                        "requisition_id": str(requisition_id),
                        "match_score": float(score),
                        "match_breakdown": {
                            "embedding_similarity": float(score),
                        },
                        "is_recommended": score >= 0.7,
                    }

                    if store_result:
                        await self._store_match_result(tenant_id, match_result)

                    return match_result

                # If RPC doesn't exist, return without score
                return {
                    "match_score": 0.0,
                    "error": "Similarity computation RPC not available",
                }

        except Exception as e:
            print(f"Error computing match score: {e}")
            return {
                "match_score": 0.0,
                "error": str(e),
            }

    async def _store_match_result(
        self,
        tenant_id: UUID,
        match_result: dict,
    ) -> bool:
        """Store or update a match result in the database."""
        try:
            async with httpx.AsyncClient() as client:
                # Upsert the match result
                data = {
                    "tenant_id": str(tenant_id),
                    "candidate_id": match_result["candidate_id"],
                    "requisition_id": match_result["requisition_id"],
                    "match_score": match_result["match_score"],
                    "match_breakdown": match_result.get("match_breakdown", {}),
                    "is_recommended": match_result.get("is_recommended", False),
                }

                # Check if exists first
                check_response = await client.get(
                    f"{self.supabase_url}/rest/v1/candidate_matches",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "candidate_id": f"eq.{match_result['candidate_id']}",
                        "requisition_id": f"eq.{match_result['requisition_id']}",
                        "select": "id",
                    },
                    timeout=10,
                )

                if check_response.status_code == 200 and check_response.json():
                    # Update existing
                    existing_id = check_response.json()[0]["id"]
                    response = await client.patch(
                        f"{self.supabase_url}/rest/v1/candidate_matches",
                        headers=self._get_headers(),
                        params={"id": f"eq.{existing_id}"},
                        json=data,
                        timeout=15,
                    )
                else:
                    # Insert new
                    response = await client.post(
                        f"{self.supabase_url}/rest/v1/candidate_matches",
                        headers=self._get_headers(),
                        json=data,
                        timeout=15,
                    )

                return response.status_code in (200, 201)

        except Exception as e:
            print(f"Error storing match result: {e}")
            return False

    async def get_recommended_candidates(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        limit: int = 10,
    ) -> list[dict]:
        """Get candidates that have been marked as recommended for a job.

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            limit: Maximum number to return

        Returns:
            List of recommended candidates
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/candidate_matches",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "requisition_id": f"eq.{requisition_id}",
                        "is_recommended": "eq.true",
                        "order": "match_score.desc",
                        "limit": str(limit),
                        "select": "*,candidates(id,email,phone,source,skills_extracted,experience_years,current_company,current_title)",
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    return response.json()

                return []

        except Exception as e:
            print(f"Error getting recommended candidates: {e}")
            return []

    async def batch_compute_matches(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        candidate_ids: Optional[list[UUID]] = None,
    ) -> dict:
        """Batch compute match scores for multiple candidates against a job.

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            candidate_ids: List of candidate IDs (None = all candidates with embeddings)

        Returns:
            Summary of batch computation
        """
        try:
            # If no candidate_ids provided, get all candidates with embeddings
            if candidate_ids is None:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.supabase_url}/rest/v1/candidate_embeddings",
                        headers=self._get_headers(),
                        params={
                            "tenant_id": f"eq.{tenant_id}",
                            "embedding_type": "eq.resume_full",
                            "select": "candidate_id",
                        },
                        timeout=15,
                    )

                    if response.status_code == 200:
                        candidate_ids = [
                            UUID(c["candidate_id"]) for c in response.json()
                        ]
                    else:
                        return {"error": "Failed to fetch candidates", "computed": 0}

            computed = 0
            errors = 0

            for candidate_id in candidate_ids:
                result = await self.compute_match_score(
                    tenant_id, candidate_id, requisition_id, store_result=True
                )
                if result and not result.get("error"):
                    computed += 1
                else:
                    errors += 1

            return {
                "computed": computed,
                "errors": errors,
                "total": len(candidate_ids),
            }

        except Exception as e:
            print(f"Error in batch compute: {e}")
            return {"error": str(e), "computed": 0}


# Singleton instance
_matching_service: Optional[MatchingService] = None


def get_matching_service() -> MatchingService:
    """Get or create the matching service singleton."""
    global _matching_service
    if _matching_service is None:
        _matching_service = MatchingService()
    return _matching_service
