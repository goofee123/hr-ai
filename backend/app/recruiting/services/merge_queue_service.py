"""Merge Queue Service.

Handles duplicate candidate review workflow:
1. Detect duplicates for a candidate
2. Add pairs to review queue
3. Merge candidates (combine data)
4. Reject as not duplicates
5. Defer for later review

Match Types:
- hard: Auto-merge (same email) - 95%+ confidence
- strong: Highly confident match (same LinkedIn, phone) - 90%+
- fuzzy: Embedding/name similarity - 80-89%
- review: Needs human review - 60-79%
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.core.supabase_client import get_supabase_client
from app.recruiting.services.candidate_deduplication import (
    CandidateDeduplicationService,
    MatchConfidence,
)
from app.recruiting.schemas.merge_queue import (
    CandidateSummary,
    DuplicateMatchReason,
    MergeQueueItemDetail,
    MergeQueueListResponse,
    MergeResultResponse,
    DetectDuplicatesResponse,
)

logger = logging.getLogger(__name__)


class MergeQueueService:
    """Service for managing the merge queue and duplicate review workflow."""

    def __init__(self):
        self.client = get_supabase_client()
        self.dedup_service = CandidateDeduplicationService()

    def _confidence_to_match_type(self, confidence: MatchConfidence) -> str:
        """Convert confidence level to match type string."""
        mapping = {
            MatchConfidence.EXACT: "hard",
            MatchConfidence.HIGH: "strong",
            MatchConfidence.MEDIUM: "fuzzy",
            MatchConfidence.LOW: "review",
            MatchConfidence.NONE: "review",
        }
        return mapping.get(confidence, "review")

    def _match_score_to_type(self, score: float) -> str:
        """Convert numeric match score to type."""
        if score >= 0.95:
            return "hard"
        elif score >= 0.90:
            return "strong"
        elif score >= 0.80:
            return "fuzzy"
        else:
            return "review"

    async def _build_candidate_summary(
        self, tenant_id: UUID, candidate_id: str
    ) -> Optional[CandidateSummary]:
        """Build a CandidateSummary from candidate data."""
        candidate = await self.client.select(
            "candidates",
            "*",
            filters={"id": candidate_id, "tenant_id": str(tenant_id)},
            single=True,
        )

        if not candidate:
            return None

        # Get application count
        applications = await self.client.select(
            "applications",
            "id",
            filters={"candidate_id": candidate_id},
        ) or []

        # Get primary resume for parsed data
        resume = await self.client.select(
            "resumes",
            "parsed_data",
            filters={"candidate_id": candidate_id, "is_primary": True},
            single=True,
        )

        parsed_data = resume.get("parsed_data", {}) if resume else {}

        return CandidateSummary(
            id=UUID(candidate["id"]),
            first_name=candidate.get("first_name", ""),
            last_name=candidate.get("last_name", ""),
            email=candidate.get("email"),
            phone=candidate.get("phone"),
            linkedin_url=candidate.get("linkedin_url"),
            current_title=parsed_data.get("current_title") or candidate.get("current_title"),
            current_company=parsed_data.get("current_company") or candidate.get("current_company"),
            years_experience=parsed_data.get("total_years_experience"),
            skills=candidate.get("skills", []) or [],
            source=candidate.get("source"),
            created_at=datetime.fromisoformat(candidate["created_at"].replace("Z", "+00:00")),
            application_count=len(applications),
        )

    async def list_queue_items(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None,
        match_type_filter: Optional[str] = None,
    ) -> MergeQueueListResponse:
        """Get paginated list of merge queue items with candidate summaries."""

        # Build filters
        filters: dict[str, Any] = {"tenant_id": str(tenant_id)}
        if status_filter:
            filters["status"] = status_filter
        if match_type_filter:
            filters["match_type"] = match_type_filter

        # Wrap entire query block in try/except for graceful handling
        try:
            # Get total count
            all_items = await self.client.select(
                "candidate_merge_queue",
                "id",
                filters=filters,
            ) or []
            total = len(all_items)

            # Get status counts
            all_statuses = await self.client.select(
                "candidate_merge_queue",
                "status",
                filters={"tenant_id": str(tenant_id)},
            ) or []

            stats = {}
            for item in all_statuses:
                status = item.get("status", "pending")
                stats[status] = stats.get(status, 0) + 1

            # Get paginated items
            offset = (page - 1) * page_size
            items = await self.client.select(
                "candidate_merge_queue",
                "*",
                filters=filters,
                order="created_at.desc",
                offset=offset,
                limit=page_size,
            ) or []
        except Exception as e:
            # Table might not exist yet - return empty response
            logger.warning(f"Error querying candidate_merge_queue: {e}")
            return MergeQueueListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                stats={"pending": 0, "merged": 0, "rejected": 0, "deferred": 0},
            )

        # Build detailed items with candidate summaries
        detailed_items = []
        for item in items:
            primary_summary = await self._build_candidate_summary(
                tenant_id, item["primary_candidate_id"]
            )
            duplicate_summary = await self._build_candidate_summary(
                tenant_id, item["duplicate_candidate_id"]
            )

            if primary_summary and duplicate_summary:
                # Parse reasons from JSONB
                raw_reasons = item.get("match_reasons", [])
                reasons = []
                for r in raw_reasons:
                    if isinstance(r, dict):
                        reasons.append(DuplicateMatchReason(
                            type=r.get("type", "name_similarity"),
                            confidence=r.get("confidence", 0.5),
                            detail=r.get("detail"),
                        ))
                    elif isinstance(r, str):
                        reasons.append(DuplicateMatchReason(
                            type="name_similarity",
                            confidence=0.7,
                            detail=r,
                        ))

                detailed_items.append(MergeQueueItemDetail(
                    id=UUID(item["id"]),
                    tenant_id=tenant_id,
                    primary_candidate_id=UUID(item["primary_candidate_id"]),
                    duplicate_candidate_id=UUID(item["duplicate_candidate_id"]),
                    match_score=item.get("match_score", 0.5),
                    match_type=item.get("match_type", "review"),
                    reasons=reasons,
                    status=item.get("status", "pending"),
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                    reviewed_at=datetime.fromisoformat(item["reviewed_at"].replace("Z", "+00:00")) if item.get("reviewed_at") else None,
                    reviewed_by=UUID(item["reviewed_by"]) if item.get("reviewed_by") else None,
                    review_notes=item.get("review_notes"),
                    primary_candidate=primary_summary,
                    duplicate_candidate=duplicate_summary,
                ))

        total_pages = (total + page_size - 1) // page_size

        return MergeQueueListResponse(
            items=detailed_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            stats=stats,
        )

    async def get_queue_item(
        self, tenant_id: UUID, item_id: UUID
    ) -> Optional[MergeQueueItemDetail]:
        """Get a single merge queue item with full details."""
        item = await self.client.select(
            "candidate_merge_queue",
            "*",
            filters={"id": str(item_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not item:
            return None

        primary_summary = await self._build_candidate_summary(
            tenant_id, item["primary_candidate_id"]
        )
        duplicate_summary = await self._build_candidate_summary(
            tenant_id, item["duplicate_candidate_id"]
        )

        if not primary_summary or not duplicate_summary:
            return None

        # Parse reasons
        raw_reasons = item.get("match_reasons", [])
        reasons = []
        for r in raw_reasons:
            if isinstance(r, dict):
                reasons.append(DuplicateMatchReason(
                    type=r.get("type", "name_similarity"),
                    confidence=r.get("confidence", 0.5),
                    detail=r.get("detail"),
                ))
            elif isinstance(r, str):
                reasons.append(DuplicateMatchReason(
                    type="name_similarity",
                    confidence=0.7,
                    detail=r,
                ))

        return MergeQueueItemDetail(
            id=UUID(item["id"]),
            tenant_id=tenant_id,
            primary_candidate_id=UUID(item["primary_candidate_id"]),
            duplicate_candidate_id=UUID(item["duplicate_candidate_id"]),
            match_score=item.get("match_score", 0.5),
            match_type=item.get("match_type", "review"),
            reasons=reasons,
            status=item.get("status", "pending"),
            created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
            reviewed_at=datetime.fromisoformat(item["reviewed_at"].replace("Z", "+00:00")) if item.get("reviewed_at") else None,
            reviewed_by=UUID(item["reviewed_by"]) if item.get("reviewed_by") else None,
            review_notes=item.get("review_notes"),
            primary_candidate=primary_summary,
            duplicate_candidate=duplicate_summary,
        )

    async def detect_duplicates(
        self,
        tenant_id: UUID,
        candidate_id: UUID,
        min_confidence: float = 0.6,
    ) -> DetectDuplicatesResponse:
        """Find potential duplicates for a candidate without adding to queue."""

        # Get the candidate
        candidate = await self.client.select(
            "candidates",
            "*",
            filters={"id": str(candidate_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not candidate:
            return DetectDuplicatesResponse(
                candidate_id=candidate_id,
                duplicates=[],
                auto_merge_count=0,
                review_count=0,
            )

        # Get candidate's resume for experience data
        resume = await self.client.select(
            "resumes",
            "parsed_data",
            filters={"candidate_id": str(candidate_id), "is_primary": True},
            single=True,
        )
        parsed_experience = resume.get("parsed_data", {}).get("experience", []) if resume else []

        # Find duplicates using the deduplication service
        result = await self.dedup_service.find_duplicates(
            tenant_id=tenant_id,
            email=candidate.get("email"),
            phone=candidate.get("phone"),
            linkedin_url=candidate.get("linkedin_url"),
            first_name=candidate.get("first_name", ""),
            last_name=candidate.get("last_name", ""),
            parsed_experience=parsed_experience,
            exclude_candidate_id=candidate_id,
        )

        duplicates = []
        auto_merge_count = 0
        review_count = 0

        if result.is_duplicate and result.existing_candidate_id:
            # Build queue item detail
            match_type = self._confidence_to_match_type(result.confidence)

            # Convert match score from confidence
            score_mapping = {
                MatchConfidence.EXACT: 0.98,
                MatchConfidence.HIGH: 0.92,
                MatchConfidence.MEDIUM: 0.82,
                MatchConfidence.LOW: 0.65,
            }
            match_score = score_mapping.get(result.confidence, 0.5)

            if match_score >= min_confidence:
                primary_summary = await self._build_candidate_summary(
                    tenant_id, str(candidate_id)
                )
                duplicate_summary = await self._build_candidate_summary(
                    tenant_id, str(result.existing_candidate_id)
                )

                if primary_summary and duplicate_summary:
                    # Build reasons
                    reasons = []
                    for reason_text in result.match_reasons:
                        reason_type = "name_similarity"
                        confidence = 0.7

                        if "Email" in reason_text:
                            reason_type = "email_match"
                            confidence = 0.99
                        elif "Phone" in reason_text:
                            reason_type = "phone_match"
                            confidence = 0.95
                        elif "LinkedIn" in reason_text:
                            reason_type = "linkedin_match"
                            confidence = 0.95
                        elif "work history" in reason_text.lower():
                            reason_type = "company_overlap"
                            confidence = 0.85

                        reasons.append(DuplicateMatchReason(
                            type=reason_type,
                            confidence=confidence,
                            detail=reason_text,
                        ))

                    item_detail = MergeQueueItemDetail(
                        id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder since not in DB
                        tenant_id=tenant_id,
                        primary_candidate_id=candidate_id,
                        duplicate_candidate_id=result.existing_candidate_id,
                        match_score=match_score,
                        match_type=match_type,
                        reasons=reasons,
                        status="pending",
                        created_at=datetime.utcnow(),
                        reviewed_at=None,
                        reviewed_by=None,
                        review_notes=None,
                        primary_candidate=primary_summary,
                        duplicate_candidate=duplicate_summary,
                    )
                    duplicates.append(item_detail)

                    if match_type == "hard":
                        auto_merge_count += 1
                    else:
                        review_count += 1

        return DetectDuplicatesResponse(
            candidate_id=candidate_id,
            duplicates=duplicates,
            auto_merge_count=auto_merge_count,
            review_count=review_count,
        )

    async def scan_all_candidates(
        self,
        tenant_id: UUID,
        limit: int = 100,
        add_to_queue: bool = True,
        triggered_by: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Scan all candidates for duplicates and optionally add to queue."""

        # Get candidates
        candidates = await self.client.select(
            "candidates",
            "id, first_name, last_name, email, phone, linkedin_url",
            filters={"tenant_id": str(tenant_id)},
            limit=limit,
        ) or []

        candidates_scanned = len(candidates)
        duplicates_found = 0
        items_added = 0

        # Get existing queue items to avoid duplicates
        existing_pairs = set()
        existing_items = await self.client.select(
            "candidate_merge_queue",
            "primary_candidate_id, duplicate_candidate_id",
            filters={"tenant_id": str(tenant_id), "status": "pending"},
        ) or []

        for item in existing_items:
            pair = tuple(sorted([item["primary_candidate_id"], item["duplicate_candidate_id"]]))
            existing_pairs.add(pair)

        # Check each candidate against others
        for i, candidate in enumerate(candidates):
            result = await self.dedup_service.find_duplicates(
                tenant_id=tenant_id,
                email=candidate.get("email"),
                phone=candidate.get("phone"),
                linkedin_url=candidate.get("linkedin_url"),
                first_name=candidate.get("first_name", ""),
                last_name=candidate.get("last_name", ""),
                exclude_candidate_id=UUID(candidate["id"]),
            )

            if result.is_duplicate and result.existing_candidate_id:
                # Check if pair already in queue
                pair = tuple(sorted([candidate["id"], str(result.existing_candidate_id)]))
                if pair in existing_pairs:
                    continue

                duplicates_found += 1
                existing_pairs.add(pair)

                if add_to_queue:
                    # Determine match type and score
                    match_type = self._confidence_to_match_type(result.confidence)
                    score_mapping = {
                        MatchConfidence.EXACT: 0.98,
                        MatchConfidence.HIGH: 0.92,
                        MatchConfidence.MEDIUM: 0.82,
                        MatchConfidence.LOW: 0.65,
                    }
                    match_score = score_mapping.get(result.confidence, 0.5)

                    # Build reasons as JSON
                    reasons = []
                    for reason_text in result.match_reasons:
                        reason_type = "name_similarity"
                        confidence = 0.7

                        if "Email" in reason_text:
                            reason_type = "email_match"
                            confidence = 0.99
                        elif "Phone" in reason_text:
                            reason_type = "phone_match"
                            confidence = 0.95
                        elif "LinkedIn" in reason_text:
                            reason_type = "linkedin_match"
                            confidence = 0.95
                        elif "work history" in reason_text.lower():
                            reason_type = "company_overlap"
                            confidence = 0.85

                        reasons.append({
                            "type": reason_type,
                            "confidence": confidence,
                            "detail": reason_text,
                        })

                    # Insert into queue
                    await self.client.insert(
                        "candidate_merge_queue",
                        {
                            "tenant_id": str(tenant_id),
                            "primary_candidate_id": candidate["id"],
                            "duplicate_candidate_id": str(result.existing_candidate_id),
                            "match_score": match_score,
                            "match_type": match_type,
                            "match_reasons": reasons,
                            "status": "pending",
                        },
                    )
                    items_added += 1

        return {
            "candidates_scanned": candidates_scanned,
            "duplicates_found": duplicates_found,
            "items_added": items_added,
        }

    async def merge_candidates(
        self,
        tenant_id: UUID,
        primary_candidate_id: UUID,
        duplicate_candidate_id: UUID,
        merge_queue_item_id: Optional[UUID] = None,
        merge_strategy: str = "smart_merge",
        merged_by: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> MergeResultResponse:
        """Merge two candidates, keeping the primary and absorbing the duplicate."""

        # Get duplicate candidate data
        duplicate = await self.client.select(
            "candidates",
            "*",
            filters={"id": str(duplicate_candidate_id), "tenant_id": str(tenant_id)},
            single=True,
        )

        if not duplicate:
            raise ValueError(f"Duplicate candidate {duplicate_candidate_id} not found")

        # Get duplicate's resume for merge
        duplicate_resume = await self.client.select(
            "resumes",
            "*",
            filters={"candidate_id": str(duplicate_candidate_id), "is_primary": True},
            single=True,
        )

        resume_data = None
        if duplicate_resume:
            resume_data = {
                "file_name": duplicate_resume.get("file_name"),
                "file_path": duplicate_resume.get("file_path"),
                "file_size_bytes": duplicate_resume.get("file_size_bytes"),
                "mime_type": duplicate_resume.get("mime_type"),
                "parsed_data": duplicate_resume.get("parsed_data"),
                "parsing_status": "completed",
            }

        # Use deduplication service to merge
        merge_result = await self.dedup_service.merge_candidate_profiles(
            tenant_id=tenant_id,
            existing_candidate_id=primary_candidate_id,
            new_candidate_data={
                "phone": duplicate.get("phone"),
                "linkedin_url": duplicate.get("linkedin_url"),
                "skills": duplicate.get("skills"),
                "tags": duplicate.get("tags"),
                "source": duplicate.get("source"),
            },
            new_resume_data=resume_data,
            merge_strategy=merge_strategy,
        )

        # Move applications from duplicate to primary
        await self.client.update(
            "applications",
            {"candidate_id": str(primary_candidate_id)},
            filters={"candidate_id": str(duplicate_candidate_id)},
        )

        # Move observations from duplicate to primary
        await self.client.update(
            "candidate_observations",
            {"candidate_id": str(primary_candidate_id)},
            filters={"candidate_id": str(duplicate_candidate_id)},
        )

        # Move activity events from duplicate to primary
        await self.client.update(
            "candidate_activity_events",
            {"candidate_id": str(primary_candidate_id)},
            filters={"candidate_id": str(duplicate_candidate_id)},
        )

        # Soft-delete the duplicate candidate
        await self.client.update(
            "candidates",
            {"deleted_at": datetime.utcnow().isoformat()},
            filters={"id": str(duplicate_candidate_id)},
        )

        # Update queue item if provided
        if merge_queue_item_id:
            await self.client.update(
                "candidate_merge_queue",
                {
                    "status": "merged",
                    "reviewed_by": str(merged_by) if merged_by else None,
                    "reviewed_at": datetime.utcnow().isoformat(),
                    "review_notes": notes,
                },
                filters={"id": str(merge_queue_item_id)},
            )

        # Build changes summary
        changes_applied = {
            "applications_moved": True,
            "observations_moved": True,
            "activity_moved": True,
            "duplicate_deleted": True,
        }
        if resume_data:
            changes_applied["resume_added"] = True

        return MergeResultResponse(
            success=True,
            primary_candidate_id=primary_candidate_id,
            merged_candidate_id=duplicate_candidate_id,
            merge_strategy=merge_strategy,
            changes_applied=changes_applied,
            new_resume_id=UUID(merge_result["new_resume_id"]) if merge_result.get("new_resume_id") else None,
            resume_version=merge_result.get("resume_version"),
        )

    async def reject_duplicate(
        self,
        tenant_id: UUID,
        merge_queue_item_id: UUID,
        rejected_by: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Mark a merge queue item as not actually duplicates."""
        result = await self.client.update(
            "candidate_merge_queue",
            {
                "status": "rejected",
                "reviewed_by": str(rejected_by) if rejected_by else None,
                "reviewed_at": datetime.utcnow().isoformat(),
                "review_notes": reason,
            },
            filters={"id": str(merge_queue_item_id), "tenant_id": str(tenant_id)},
        )
        return result is not None

    async def defer_duplicate(
        self,
        tenant_id: UUID,
        merge_queue_item_id: UUID,
        deferred_by: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Defer a merge decision for later review."""
        result = await self.client.update(
            "candidate_merge_queue",
            {
                "status": "deferred",
                "reviewed_by": str(deferred_by) if deferred_by else None,
                "reviewed_at": datetime.utcnow().isoformat(),
                "review_notes": notes,
            },
            filters={"id": str(merge_queue_item_id), "tenant_id": str(tenant_id)},
        )
        return result is not None

    async def get_queue_stats(self, tenant_id: UUID) -> dict[str, Any]:
        """Get summary statistics for the merge queue."""
        try:
            items = await self.client.select(
                "candidate_merge_queue",
                "status, match_type",
                filters={"tenant_id": str(tenant_id)},
            ) or []
        except Exception as e:
            # Table might not exist yet - return empty stats
            logger.warning(f"Error querying candidate_merge_queue stats: {e}")
            return {
                "total": 0,
                "by_status": {"pending": 0, "merged": 0, "rejected": 0, "deferred": 0},
                "by_match_type": {"hard": 0, "strong": 0, "fuzzy": 0, "review": 0},
                "pending_auto_merge": 0,
                "pending_review": 0,
                "table_not_found": True,
            }

        stats = {
            "total": len(items),
            "by_status": {},
            "by_match_type": {},
            "pending_auto_merge": 0,
            "pending_review": 0,
        }

        for item in items:
            status = item.get("status", "pending")
            match_type = item.get("match_type", "review")

            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_match_type"][match_type] = stats["by_match_type"].get(match_type, 0) + 1

            if status == "pending":
                if match_type == "hard":
                    stats["pending_auto_merge"] += 1
                else:
                    stats["pending_review"] += 1

        return stats


# Singleton factory
_merge_queue_service = None


def get_merge_queue_service() -> MergeQueueService:
    """Get or create the merge queue service singleton."""
    global _merge_queue_service
    if _merge_queue_service is None:
        _merge_queue_service = MergeQueueService()
    return _merge_queue_service
