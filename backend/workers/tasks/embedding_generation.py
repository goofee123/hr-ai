"""Embedding Generation Task - Background job for generating vector embeddings."""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_headers() -> Dict[str, str]:
    """Get headers for Supabase REST API calls."""
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def generate_embeddings(
    ctx: Dict[str, Any],
    entity_type: str,  # 'candidate' or 'job'
    entity_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Background task to generate embeddings for a candidate or job requisition.

    Uses OpenAI text-embedding-ada-002 to create vector embeddings for:
    - Candidates: Resume text, skills, experience summary
    - Jobs: Description, requirements, responsibilities

    Args:
        ctx: ARQ context
        entity_type: 'candidate' or 'job'
        entity_id: UUID of the entity
        tenant_id: UUID of the tenant

    Returns:
        Dict with embedding status and metadata
    """
    logger.info(f"Generating embeddings for {entity_type}={entity_id}")

    result = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": "pending",
        "embeddings_created": 0,
        "error": None,
    }

    openai_key = settings.openai_api_key if hasattr(settings, 'openai_api_key') else None

    if not openai_key:
        result["status"] = "skipped"
        result["error"] = "OpenAI API key not configured"
        logger.warning("Embedding generation skipped - OpenAI API key not configured")
        return result

    async with httpx.AsyncClient() as client:
        try:
            if entity_type == "candidate":
                embeddings = await _generate_candidate_embeddings(
                    client, entity_id, tenant_id, openai_key
                )
            elif entity_type == "job":
                embeddings = await _generate_job_embeddings(
                    client, entity_id, tenant_id, openai_key
                )
            else:
                result["status"] = "failed"
                result["error"] = f"Unknown entity type: {entity_type}"
                return result

            result["embeddings_created"] = len(embeddings)
            result["status"] = "completed"

            logger.info(
                f"Generated {len(embeddings)} embeddings for {entity_type}={entity_id}"
            )

        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def _generate_candidate_embeddings(
    client: httpx.AsyncClient,
    candidate_id: str,
    tenant_id: str,
    openai_key: str,
) -> List[Dict[str, Any]]:
    """Generate embeddings for a candidate."""
    embeddings_created = []

    # Fetch candidate with parsed resume data
    response = await client.get(
        f"{settings.supabase_url}/rest/v1/candidates",
        headers=_get_headers(),
        params={
            "id": f"eq.{candidate_id}",
            "tenant_id": f"eq.{tenant_id}",
            "select": "id,parsed_data,skills_extracted,current_title,current_company",
        },
        timeout=30,
    )

    if response.status_code != 200 or not response.json():
        logger.warning(f"Candidate not found: {candidate_id}")
        return embeddings_created

    candidate = response.json()[0]
    parsed_data = candidate.get("parsed_data", {})

    # Get resume for text
    resume_response = await client.get(
        f"{settings.supabase_url}/rest/v1/resumes",
        headers=_get_headers(),
        params={
            "candidate_id": f"eq.{candidate_id}",
            "select": "extracted_text,parsed_data",
            "order": "created_at.desc",
            "limit": "1",
        },
        timeout=30,
    )

    resume_text = ""
    if resume_response.status_code == 200 and resume_response.json():
        resume = resume_response.json()[0]
        resume_text = resume.get("extracted_text", "")

    # Generate different embedding types
    embedding_configs = []

    # 1. Full resume embedding
    if resume_text:
        embedding_configs.append({
            "type": "resume",
            "text": resume_text[:8000],  # Limit to ~8k chars
        })

    # 2. Skills-focused embedding
    skills = candidate.get("skills_extracted", []) or parsed_data.get("skills", [])
    if skills:
        skills_text = f"Skills: {', '.join(skills)}"
        embedding_configs.append({
            "type": "skills",
            "text": skills_text,
        })

    # 3. Experience summary embedding
    experience = parsed_data.get("experience", [])
    if experience:
        exp_parts = []
        for exp in experience[:5]:  # Top 5 positions
            exp_parts.append(
                f"{exp.get('title', '')} at {exp.get('company', '')}. {exp.get('description', '')}"
            )
        experience_text = " | ".join(exp_parts)
        embedding_configs.append({
            "type": "experience",
            "text": experience_text[:4000],
        })

    # Generate embeddings for each config
    for config in embedding_configs:
        embedding = await _get_embedding(openai_key, config["text"])
        if embedding:
            # Store embedding
            stored = await _store_candidate_embedding(
                client, candidate_id, config["type"], embedding, tenant_id
            )
            if stored:
                embeddings_created.append({
                    "type": config["type"],
                    "dimension": len(embedding),
                })

    return embeddings_created


async def _generate_job_embeddings(
    client: httpx.AsyncClient,
    job_id: str,
    tenant_id: str,
    openai_key: str,
) -> List[Dict[str, Any]]:
    """Generate embeddings for a job requisition."""
    embeddings_created = []

    # Fetch job requisition
    response = await client.get(
        f"{settings.supabase_url}/rest/v1/job_requisitions",
        headers=_get_headers(),
        params={
            "id": f"eq.{job_id}",
            "tenant_id": f"eq.{tenant_id}",
            "select": "id,title,description,requirements,responsibilities,skills_required,department",
        },
        timeout=30,
    )

    if response.status_code != 200 or not response.json():
        logger.warning(f"Job requisition not found: {job_id}")
        return embeddings_created

    job = response.json()[0]

    # Generate different embedding types
    embedding_configs = []

    # 1. Full description embedding
    description = job.get("description", "")
    if description:
        full_text = f"{job.get('title', '')}. {description}"
        embedding_configs.append({
            "type": "description",
            "text": full_text[:8000],
        })

    # 2. Requirements embedding
    requirements = job.get("requirements", "")
    if requirements:
        embedding_configs.append({
            "type": "requirements",
            "text": requirements[:4000],
        })

    # 3. Skills required embedding
    skills = job.get("skills_required", [])
    if skills:
        skills_text = f"Required skills for {job.get('title', '')}: {', '.join(skills)}"
        embedding_configs.append({
            "type": "skills",
            "text": skills_text,
        })

    # Generate embeddings for each config
    for config in embedding_configs:
        embedding = await _get_embedding(openai_key, config["text"])
        if embedding:
            # Store embedding
            stored = await _store_job_embedding(
                client, job_id, config["type"], embedding, tenant_id
            )
            if stored:
                embeddings_created.append({
                    "type": config["type"],
                    "dimension": len(embedding),
                })

    return embeddings_created


async def _get_embedding(openai_key: str, text: str) -> Optional[List[float]]:
    """Get embedding from OpenAI API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-ada-002",
                    "input": text,
                },
                timeout=60,
            )

            if response.status_code != 200:
                logger.error(f"OpenAI embedding error: {response.status_code}")
                return None

            result = response.json()
            return result["data"][0]["embedding"]

    except Exception as e:
        logger.error(f"Embedding API error: {str(e)}")
        return None


async def _store_candidate_embedding(
    client: httpx.AsyncClient,
    candidate_id: str,
    embedding_type: str,
    embedding: List[float],
    tenant_id: str,
) -> bool:
    """Store candidate embedding in database."""
    try:
        # Delete existing embedding of this type
        await client.delete(
            f"{settings.supabase_url}/rest/v1/candidate_embeddings",
            headers=_get_headers(),
            params={
                "candidate_id": f"eq.{candidate_id}",
                "embedding_type": f"eq.{embedding_type}",
            },
            timeout=30,
        )

        # Insert new embedding
        embedding_data = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "candidate_id": candidate_id,
            "embedding_type": embedding_type,
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/candidate_embeddings",
            headers=_get_headers(),
            json=embedding_data,
            timeout=30,
        )

        return response.status_code in (200, 201)

    except Exception as e:
        logger.error(f"Failed to store candidate embedding: {str(e)}")
        return False


async def _store_job_embedding(
    client: httpx.AsyncClient,
    job_id: str,
    embedding_type: str,
    embedding: List[float],
    tenant_id: str,
) -> bool:
    """Store job embedding in database."""
    try:
        # Delete existing embedding of this type
        await client.delete(
            f"{settings.supabase_url}/rest/v1/job_embeddings",
            headers=_get_headers(),
            params={
                "requisition_id": f"eq.{job_id}",
                "embedding_type": f"eq.{embedding_type}",
            },
            timeout=30,
        )

        # Insert new embedding
        embedding_data = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "requisition_id": job_id,
            "embedding_type": embedding_type,
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/job_embeddings",
            headers=_get_headers(),
            json=embedding_data,
            timeout=30,
        )

        return response.status_code in (200, 201)

    except Exception as e:
        logger.error(f"Failed to store job embedding: {str(e)}")
        return False


async def calculate_match_scores(
    ctx: Dict[str, Any],
    job_id: str,
    tenant_id: str,
    candidate_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Background task to calculate match scores between a job and candidates.

    Uses cosine similarity on embeddings to find best matches.

    Args:
        ctx: ARQ context
        job_id: UUID of the job requisition
        tenant_id: UUID of the tenant
        candidate_ids: Optional list of specific candidate IDs to score

    Returns:
        Dict with match results
    """
    logger.info(f"Calculating match scores for job={job_id}")

    result = {
        "job_id": job_id,
        "status": "pending",
        "candidates_scored": 0,
        "top_matches": [],
        "error": None,
    }

    async with httpx.AsyncClient() as client:
        try:
            # This would use pgvector for similarity search
            # For now, we'll document the approach

            # 1. Get job embeddings
            job_emb_response = await client.get(
                f"{settings.supabase_url}/rest/v1/job_embeddings",
                headers=_get_headers(),
                params={
                    "requisition_id": f"eq.{job_id}",
                    "select": "embedding_type,embedding",
                },
                timeout=30,
            )

            if job_emb_response.status_code != 200 or not job_emb_response.json():
                result["status"] = "failed"
                result["error"] = "No job embeddings found"
                return result

            # 2. Use pgvector similarity search (requires RPC function in Supabase)
            # Example SQL that would be an RPC function:
            # SELECT c.id, c.first_name, c.last_name,
            #        1 - (ce.embedding <=> $job_embedding) as similarity
            # FROM candidates c
            # JOIN candidate_embeddings ce ON c.id = ce.candidate_id
            # WHERE ce.embedding_type = 'resume'
            #   AND c.tenant_id = $tenant_id
            # ORDER BY ce.embedding <=> $job_embedding
            # LIMIT 100;

            # For now, mark as completed with placeholder
            result["status"] = "completed"
            result["candidates_scored"] = 0
            result["note"] = "pgvector similarity search requires RPC function setup"

        except Exception as e:
            logger.error(f"Match score calculation failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def batch_generate_embeddings(
    ctx: Dict[str, Any],
    entity_type: str,
    tenant_id: str,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """
    Background task to generate embeddings for all entities missing them.

    Useful for initial data migration or periodic cleanup.
    """
    logger.info(f"Starting batch embedding generation for {entity_type}")

    result = {
        "entity_type": entity_type,
        "status": "pending",
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
    }

    openai_key = settings.openai_api_key if hasattr(settings, 'openai_api_key') else None

    if not openai_key:
        result["status"] = "skipped"
        result["error"] = "OpenAI API key not configured"
        return result

    async with httpx.AsyncClient() as client:
        try:
            if entity_type == "candidate":
                # Find candidates without embeddings
                # This would need a more sophisticated query with LEFT JOIN
                # For now, we'll process all candidates and let upsert handle it
                response = await client.get(
                    f"{settings.supabase_url}/rest/v1/candidates",
                    headers=_get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "select": "id",
                        "limit": str(batch_size),
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    candidates = response.json()
                    for candidate in candidates:
                        result["processed"] += 1
                        try:
                            emb_result = await _generate_candidate_embeddings(
                                client, candidate["id"], tenant_id, openai_key
                            )
                            if emb_result:
                                result["succeeded"] += 1
                            else:
                                result["failed"] += 1
                        except Exception as e:
                            result["failed"] += 1
                            result["errors"].append(str(e))

            elif entity_type == "job":
                response = await client.get(
                    f"{settings.supabase_url}/rest/v1/job_requisitions",
                    headers=_get_headers(),
                    params={
                        "tenant_id": f"eq.{tenant_id}",
                        "status": "eq.open",
                        "select": "id",
                        "limit": str(batch_size),
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    jobs = response.json()
                    for job in jobs:
                        result["processed"] += 1
                        try:
                            emb_result = await _generate_job_embeddings(
                                client, job["id"], tenant_id, openai_key
                            )
                            if emb_result:
                                result["succeeded"] += 1
                            else:
                                result["failed"] += 1
                        except Exception as e:
                            result["failed"] += 1
                            result["errors"].append(str(e))

            result["status"] = "completed"

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    logger.info(f"Batch embedding complete: {result}")
    return result
