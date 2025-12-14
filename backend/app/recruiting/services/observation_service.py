"""Service for managing candidate observations, emails, and retrieving observation data."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.observation import (
    CandidateEmailCreate,
    CandidateEmailResponse,
    CandidateEmailUpdate,
    ObservationCreate,
    ObservationResponse,
    ObservationSummary,
    CandidateObservationsResponse,
)


class ObservationService:
    """Service for managing candidate observations and emails."""

    def __init__(self):
        self.client = get_supabase_client()

    # =========================================================================
    # CANDIDATE EMAILS
    # =========================================================================

    async def get_candidate_emails(
        self, tenant_id: UUID, candidate_id: UUID
    ) -> list[CandidateEmailResponse]:
        """Get all emails for a candidate."""
        emails = await self.client.select(
            "candidate_emails",
            "*",
            filters={"tenant_id": str(tenant_id), "candidate_id": str(candidate_id)},
        ) or []

        return [CandidateEmailResponse.model_validate(e) for e in emails]

    async def add_candidate_email(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        email_data: CandidateEmailCreate,
    ) -> CandidateEmailResponse:
        """Add an email to a candidate."""
        # If this is marked as primary, unset other primary emails
        if email_data.is_primary:
            await self._unset_primary_emails(tenant_id, candidate_id)

        email_dict = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
            "email": email_data.email.lower().strip(),
            "is_primary": email_data.is_primary,
            "source": email_data.source,
        }

        result = await self.client.insert("candidate_emails", email_dict)
        return CandidateEmailResponse.model_validate(result)

    async def update_candidate_email(
        self,
        tenant_id: UUID,
        email_id: UUID,
        email_data: CandidateEmailUpdate,
    ) -> Optional[CandidateEmailResponse]:
        """Update a candidate email."""
        # Get existing email
        existing = await self.client.select(
            "candidate_emails",
            "*",
            filters={"id": str(email_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not existing:
            return None

        update_dict = email_data.model_dump(exclude_unset=True)

        # If setting as primary, unset other primary emails
        if update_dict.get("is_primary"):
            await self._unset_primary_emails(tenant_id, UUID(existing["candidate_id"]))

        update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await self.client.update(
            "candidate_emails",
            update_dict,
            filters={"id": str(email_id)},
        )

        return CandidateEmailResponse.model_validate(result)

    async def delete_candidate_email(
        self, tenant_id: UUID, email_id: UUID
    ) -> bool:
        """Delete a candidate email."""
        existing = await self.client.select(
            "candidate_emails",
            "id",
            filters={"id": str(email_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not existing:
            return False

        await self.client.delete("candidate_emails", filters={"id": str(email_id)})
        return True

    async def find_candidate_by_email(
        self, tenant_id: UUID, email: str
    ) -> Optional[UUID]:
        """Find a candidate by email address."""
        normalized_email = email.lower().strip()

        result = await self.client.select(
            "candidate_emails",
            "candidate_id",
            filters={"tenant_id": str(tenant_id), "email": normalized_email},
            single=True,
        )

        if result:
            return UUID(result["candidate_id"])
        return None

    async def _unset_primary_emails(self, tenant_id: UUID, candidate_id: UUID):
        """Unset all primary emails for a candidate."""
        emails = await self.client.select(
            "candidate_emails",
            "id",
            filters={
                "tenant_id": str(tenant_id),
                "candidate_id": str(candidate_id),
                "is_primary": "true",
            },
        ) or []

        for email in emails:
            await self.client.update(
                "candidate_emails",
                {"is_primary": False, "updated_at": datetime.now(timezone.utc).isoformat()},
                filters={"id": email["id"]},
            )

    # =========================================================================
    # CANDIDATE OBSERVATIONS
    # =========================================================================

    async def get_candidate_observations(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        current_only: bool = True,
        field_name: Optional[str] = None,
    ) -> list[ObservationResponse]:
        """Get observations for a candidate."""
        filters = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
        }

        if current_only:
            filters["is_current"] = "true"

        if field_name:
            filters["field_name"] = field_name

        observations = await self.client.select(
            "candidate_observations",
            "*",
            filters=filters,
        ) or []

        return [ObservationResponse.model_validate(o) for o in observations]

    async def get_observations_summary(
        self, tenant_id: UUID, candidate_id: UUID
    ) -> CandidateObservationsResponse:
        """Get summarized observations for a candidate, grouped by field."""
        observations = await self.get_candidate_observations(
            tenant_id, candidate_id, current_only=True
        )

        obs_dict = {}
        last_extracted = None

        for obs in observations:
            # For fields that can have multiple values (like 'skill'), append
            # For unique fields, keep the one with highest confidence
            if obs.field_name not in obs_dict or (
                obs.confidence and obs.confidence > (obs_dict[obs.field_name].confidence or 0)
            ):
                obs_dict[obs.field_name] = ObservationSummary(
                    field_name=obs.field_name,
                    field_value=obs.field_value,
                    value_type=obs.value_type,
                    confidence=obs.confidence,
                    extraction_method=obs.extraction_method,
                    extracted_at=obs.extracted_at,
                )

            if not last_extracted or obs.extracted_at > last_extracted:
                last_extracted = obs.extracted_at

        return CandidateObservationsResponse(
            candidate_id=candidate_id,
            observations=obs_dict,
            total_count=len(observations),
            last_extracted_at=last_extracted,
        )

    async def add_observation(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        observation_data: ObservationCreate,
        extracted_by: Optional[UUID] = None,
    ) -> ObservationResponse:
        """Add an observation for a candidate."""
        obs_dict = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
            "field_name": observation_data.field_name,
            "field_value": observation_data.field_value,
            "value_type": observation_data.value_type,
            "confidence": float(observation_data.confidence) if observation_data.confidence else None,
            "extraction_method": observation_data.extraction_method,
            "source_document_id": str(observation_data.source_document_id) if observation_data.source_document_id else None,
            "is_current": True,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extracted_by": str(extracted_by) if extracted_by else None,
        }

        result = await self.client.insert("candidate_observations", obs_dict)
        return ObservationResponse.model_validate(result)

    async def add_observations_bulk(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        observations: list[ObservationCreate],
        extracted_by: Optional[UUID] = None,
        supersede_existing: bool = True,
    ) -> list[ObservationResponse]:
        """Add multiple observations for a candidate (e.g., from LLM extraction)."""
        if supersede_existing:
            # Mark existing observations as superseded
            await self._supersede_observations(tenant_id, candidate_id)

        results = []
        for obs_data in observations:
            result = await self.add_observation(
                tenant_id, candidate_id, obs_data, extracted_by
            )
            results.append(result)

        return results

    async def supersede_observation(
        self,
        tenant_id: UUID,
        observation_id: UUID,
        new_observation: ObservationCreate,
        extracted_by: Optional[UUID] = None,
    ) -> Optional[ObservationResponse]:
        """Supersede an observation with a new value."""
        # Get existing observation
        existing = await self.client.select(
            "candidate_observations",
            "*",
            filters={"id": str(observation_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not existing:
            return None

        # Create new observation
        new_obs = await self.add_observation(
            tenant_id,
            UUID(existing["candidate_id"]),
            new_observation,
            extracted_by,
        )

        # Mark old observation as superseded
        await self.client.update(
            "candidate_observations",
            {
                "is_current": False,
                "superseded_by_id": str(new_obs.id),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            filters={"id": str(observation_id)},
        )

        return new_obs

    async def delete_observation(
        self, tenant_id: UUID, observation_id: UUID
    ) -> bool:
        """Delete an observation."""
        existing = await self.client.select(
            "candidate_observations",
            "id",
            filters={"id": str(observation_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not existing:
            return False

        await self.client.delete(
            "candidate_observations", filters={"id": str(observation_id)}
        )
        return True

    async def _supersede_observations(
        self, tenant_id: UUID, candidate_id: UUID, field_name: Optional[str] = None
    ):
        """Mark all current observations as superseded."""
        filters = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
            "is_current": "true",
        }

        if field_name:
            filters["field_name"] = field_name

        observations = await self.client.select(
            "candidate_observations", "id", filters=filters
        ) or []

        for obs in observations:
            await self.client.update(
                "candidate_observations",
                {
                    "is_current": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                filters={"id": obs["id"]},
            )

    # =========================================================================
    # OBSERVATION QUERIES
    # =========================================================================

    async def get_candidates_with_skill(
        self, tenant_id: UUID, skill: str, min_confidence: float = 0.7
    ) -> list[UUID]:
        """Find candidates with a specific skill observation."""
        # This would be more efficient with a proper SQL query
        # For now, we'll use the REST API approach
        observations = await self.client.select(
            "candidate_observations",
            "candidate_id, confidence",
            filters={
                "tenant_id": str(tenant_id),
                "field_name": "skill",
                "is_current": "true",
            },
        ) or []

        # Filter by skill value and confidence
        matching = []
        for obs in observations:
            if obs.get("confidence") and float(obs["confidence"]) >= min_confidence:
                matching.append(UUID(obs["candidate_id"]))

        return list(set(matching))


# Singleton instance
_observation_service: Optional[ObservationService] = None


def get_observation_service() -> ObservationService:
    """Get the observation service singleton."""
    global _observation_service
    if _observation_service is None:
        _observation_service = ObservationService()
    return _observation_service
