"""Embedding service for AI-powered candidate-job matching using OpenAI and pgvector."""

import os
from typing import Optional
from uuid import UUID

import httpx
from openai import AsyncOpenAI

from app.config import get_settings


settings = get_settings()

# OpenAI embedding model
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """Service for generating and storing embeddings for candidate matching."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.openai_client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.openai_client = None

        # Supabase REST API client
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_role_key

    def _get_headers(self) -> dict:
        """Get headers for Supabase REST API calls."""
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def generate_embedding(self, text: str) -> Optional[list[float]]:
        """Generate an embedding vector for the given text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        if not self.openai_client:
            return None

        if not text or len(text.strip()) < 10:
            return None

        try:
            # Truncate very long text
            max_chars = 8000
            truncated_text = text[:max_chars]

            response = await self.openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=truncated_text,
            )

            return response.data[0].embedding

        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    async def store_candidate_embedding(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        resume_id: Optional[UUID],
        embedding: list[float],
        embedding_type: str = "resume_full",
        source_text: Optional[str] = None,
    ) -> Optional[dict]:
        """Store a candidate embedding in the database.

        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            resume_id: Resume ID (optional)
            embedding: Embedding vector
            embedding_type: Type of embedding (resume_full, skills, experience)
            source_text: Original text used to generate embedding

        Returns:
            Created embedding record or None if failed
        """
        try:
            async with httpx.AsyncClient() as client:
                # Format embedding as PostgreSQL array string
                embedding_str = f"[{','.join(str(x) for x in embedding)}]"

                data = {
                    "tenant_id": str(tenant_id),
                    "candidate_id": str(candidate_id),
                    "resume_id": str(resume_id) if resume_id else None,
                    "embedding": embedding_str,
                    "embedding_type": embedding_type,
                    "model_used": EMBEDDING_MODEL,
                    "source_text_preview": source_text[:500] if source_text else None,
                }

                response = await client.post(
                    f"{self.supabase_url}/rest/v1/candidate_embeddings",
                    headers=self._get_headers(),
                    json=data,
                    timeout=30,
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    return result[0] if isinstance(result, list) and result else result

                print(f"Failed to store candidate embedding: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Error storing candidate embedding: {e}")
            return None

    async def store_job_embedding(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        embedding: list[float],
        embedding_type: str = "description",
        source_text: Optional[str] = None,
    ) -> Optional[dict]:
        """Store a job embedding in the database.

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            embedding: Embedding vector
            embedding_type: Type of embedding (description, requirements)
            source_text: Original text used to generate embedding

        Returns:
            Created embedding record or None if failed
        """
        try:
            async with httpx.AsyncClient() as client:
                embedding_str = f"[{','.join(str(x) for x in embedding)}]"

                data = {
                    "tenant_id": str(tenant_id),
                    "requisition_id": str(requisition_id),
                    "embedding": embedding_str,
                    "embedding_type": embedding_type,
                    "model_used": EMBEDDING_MODEL,
                    "source_text_preview": source_text[:500] if source_text else None,
                }

                response = await client.post(
                    f"{self.supabase_url}/rest/v1/job_embeddings",
                    headers=self._get_headers(),
                    json=data,
                    timeout=30,
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    return result[0] if isinstance(result, list) and result else result

                print(f"Failed to store job embedding: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Error storing job embedding: {e}")
            return None

    async def get_candidate_embedding(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        embedding_type: str = "resume_full",
    ) -> Optional[dict]:
        """Get a candidate's embedding.

        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            embedding_type: Type of embedding to retrieve

        Returns:
            Embedding record or None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/candidate_embeddings",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "candidate_id": f"eq.{candidate_id}",
                        "embedding_type": f"eq.{embedding_type}",
                        "order": "created_at.desc",
                        "limit": "1",
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    results = response.json()
                    return results[0] if results else None

                return None

        except Exception as e:
            print(f"Error getting candidate embedding: {e}")
            return None

    async def get_job_embedding(
        self,
        tenant_id: UUID,
        requisition_id: UUID,
        embedding_type: str = "description",
    ) -> Optional[dict]:
        """Get a job's embedding.

        Args:
            tenant_id: Tenant ID
            requisition_id: Job requisition ID
            embedding_type: Type of embedding to retrieve

        Returns:
            Embedding record or None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/job_embeddings",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "requisition_id": f"eq.{requisition_id}",
                        "embedding_type": f"eq.{embedding_type}",
                        "order": "created_at.desc",
                        "limit": "1",
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    results = response.json()
                    return results[0] if results else None

                return None

        except Exception as e:
            print(f"Error getting job embedding: {e}")
            return None

    async def delete_candidate_embeddings(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
    ) -> bool:
        """Delete all embeddings for a candidate.

        Args:
            tenant_id: Tenant ID
            candidate_id: Candidate ID

        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.supabase_url}/rest/v1/candidate_embeddings",
                    headers=self._get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "candidate_id": f"eq.{candidate_id}",
                    },
                    timeout=15,
                )

                return response.status_code in (200, 204)

        except Exception as e:
            print(f"Error deleting candidate embeddings: {e}")
            return False


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
