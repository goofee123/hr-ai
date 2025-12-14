"""Service for tracking candidate activity events and recruiter engagement."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.core.supabase_client import get_supabase_client
from app.recruiting.schemas.observation import (
    ActivityEventCreate,
    ActivityEventResponse,
    ActivityEventSummary,
    CandidateActivityFeed,
    EventType,
)


class ActivityTracker:
    """Service for tracking all candidate-related activity events."""

    def __init__(self):
        self.client = get_supabase_client()

    # =========================================================================
    # EVENT LOGGING
    # =========================================================================

    async def log_event(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        event_type: str,
        user_id: Optional[UUID] = None,
        application_id: Optional[UUID] = None,
        event_data: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log an activity event for a candidate."""
        event_dict = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "application_id": str(application_id) if application_id else None,
            "event_data": event_data or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        result = await self.client.insert("candidate_activity_events", event_dict)
        return ActivityEventResponse.model_validate(result)

    async def log_event_from_schema(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        event: ActivityEventCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log an activity event from a schema."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=event.event_type,
            user_id=user_id,
            application_id=event.application_id,
            event_data=event.event_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # SPECIFIC EVENT HELPERS
    # =========================================================================

    async def log_profile_viewed(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log when a recruiter views a candidate profile."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.PROFILE_VIEWED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_resume_downloaded(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        resume_id: UUID,
        ip_address: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log when a recruiter downloads a resume."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.RESUME_DOWNLOADED,
            user_id=user_id,
            event_data={"resume_id": str(resume_id)},
            ip_address=ip_address,
        )

    async def log_resume_uploaded(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: Optional[UUID],
        resume_id: UUID,
        source: str = "upload",
    ) -> ActivityEventResponse:
        """Log when a resume is uploaded."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.RESUME_UPLOADED,
            user_id=user_id,
            event_data={"resume_id": str(resume_id), "source": source},
        )

    async def log_note_added(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        note_id: UUID,
        application_id: Optional[UUID] = None,
    ) -> ActivityEventResponse:
        """Log when a recruiter adds a note."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.NOTE_ADDED,
            user_id=user_id,
            application_id=application_id,
            event_data={"note_id": str(note_id)},
        )

    async def log_stage_changed(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        application_id: UUID,
        from_stage: str,
        to_stage: str,
        reason: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log when a candidate moves to a new pipeline stage."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.STAGE_CHANGED,
            user_id=user_id,
            application_id=application_id,
            event_data={
                "from_stage": from_stage,
                "to_stage": to_stage,
                "reason": reason,
            },
        )

    async def log_interview_scheduled(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        application_id: UUID,
        interview_id: UUID,
        scheduled_at: datetime,
        interview_type: str,
    ) -> ActivityEventResponse:
        """Log when an interview is scheduled."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.INTERVIEW_SCHEDULED,
            user_id=user_id,
            application_id=application_id,
            event_data={
                "interview_id": str(interview_id),
                "scheduled_at": scheduled_at.isoformat(),
                "interview_type": interview_type,
            },
        )

    async def log_feedback_submitted(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        application_id: UUID,
        feedback_id: UUID,
        recommendation: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log when interview feedback is submitted."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.FEEDBACK_SUBMITTED,
            user_id=user_id,
            application_id=application_id,
            event_data={
                "feedback_id": str(feedback_id),
                "recommendation": recommendation,
            },
        )

    async def log_offer_extended(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        application_id: UUID,
        offer_id: UUID,
    ) -> ActivityEventResponse:
        """Log when an offer is extended."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.OFFER_EXTENDED,
            user_id=user_id,
            application_id=application_id,
            event_data={"offer_id": str(offer_id)},
        )

    async def log_rejected(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        user_id: UUID,
        application_id: UUID,
        reason_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> ActivityEventResponse:
        """Log when a candidate is rejected."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            event_type=EventType.REJECTED,
            user_id=user_id,
            application_id=application_id,
            event_data={
                "reason_id": str(reason_id) if reason_id else None,
                "notes": notes,
            },
        )

    async def log_candidate_merged(
        self,
        tenant_id: UUID,
        winner_id: UUID,
        loser_id: UUID,
        user_id: UUID,
    ) -> ActivityEventResponse:
        """Log when two candidates are merged."""
        return await self.log_event(
            tenant_id=tenant_id,
            candidate_id=winner_id,
            event_type=EventType.MERGED,
            user_id=user_id,
            event_data={"merged_from_candidate_id": str(loser_id)},
        )

    # =========================================================================
    # ACTIVITY QUERIES
    # =========================================================================

    async def get_candidate_activity(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        limit: int = 50,
        offset: int = 0,
        event_types: Optional[list[str]] = None,
    ) -> CandidateActivityFeed:
        """Get activity feed for a candidate."""
        filters = {
            "tenant_id": str(tenant_id),
            "candidate_id": str(candidate_id),
        }

        # Get all events (we'll filter/paginate in memory for now)
        events = await self.client.select(
            "candidate_activity_events",
            "*",
            filters=filters,
        ) or []

        # Sort by created_at descending
        events.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Filter by event types if specified
        if event_types:
            events = [e for e in events if e["event_type"] in event_types]

        total_count = len(events)
        has_more = (offset + limit) < total_count

        # Apply pagination
        events = events[offset:offset + limit]

        summaries = [
            ActivityEventSummary(
                event_type=e["event_type"],
                user_id=UUID(e["user_id"]) if e.get("user_id") else None,
                event_data=e.get("event_data") or {},
                created_at=datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")),
            )
            for e in events
        ]

        return CandidateActivityFeed(
            candidate_id=candidate_id,
            events=summaries,
            total_count=total_count,
            has_more=has_more,
        )

    async def get_user_recent_activity(
        self,
        tenant_id: UUID,
        user_id: UUID,
        limit: int = 50,
    ) -> list[ActivityEventResponse]:
        """Get recent activity for a specific user (recruiter dashboard)."""
        events = await self.client.select(
            "candidate_activity_events",
            "*",
            filters={
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
            },
        ) or []

        # Sort by created_at descending
        events.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Limit
        events = events[:limit]

        return [ActivityEventResponse.model_validate(e) for e in events]

    async def get_recent_views(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        days: int = 30,
    ) -> int:
        """Get count of profile views in the last N days."""
        events = await self.client.select(
            "candidate_activity_events",
            "id, created_at",
            filters={
                "tenant_id": str(tenant_id),
                "candidate_id": str(candidate_id),
                "event_type": EventType.PROFILE_VIEWED,
            },
        ) or []

        # Filter by date range
        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff = cutoff.replace(day=cutoff.day - days)

        count = 0
        for e in events:
            created = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            if created >= cutoff:
                count += 1

        return count

    async def get_engagement_metrics(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
    ) -> dict[str, Any]:
        """Get engagement metrics for a candidate."""
        events = await self.client.select(
            "candidate_activity_events",
            "event_type, created_at",
            filters={
                "tenant_id": str(tenant_id),
                "candidate_id": str(candidate_id),
            },
        ) or []

        # Count by event type
        event_counts: dict[str, int] = {}
        for e in events:
            event_type = e["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        # Calculate last activity
        last_activity = None
        if events:
            events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            last_activity = events[0]["created_at"]

        return {
            "total_events": len(events),
            "event_counts": event_counts,
            "profile_views": event_counts.get(EventType.PROFILE_VIEWED, 0),
            "resume_downloads": event_counts.get(EventType.RESUME_DOWNLOADED, 0),
            "notes_added": event_counts.get(EventType.NOTE_ADDED, 0),
            "last_activity": last_activity,
        }


# Singleton instance
_activity_tracker: Optional[ActivityTracker] = None


def get_activity_tracker() -> ActivityTracker:
    """Get the activity tracker singleton."""
    global _activity_tracker
    if _activity_tracker is None:
        _activity_tracker = ActivityTracker()
    return _activity_tracker
