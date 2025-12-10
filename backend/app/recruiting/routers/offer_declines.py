"""Offer Decline Reasons router for tracking why candidates decline offers."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.offer_decline import (
    OfferDeclineReasonCreate,
    OfferDeclineReasonResponse,
    DeclineReasonsListResponse,
    DeclineAnalytics,
    STANDARD_DECLINE_REASONS,
)


router = APIRouter()
settings = get_settings()


def _get_headers():
    """Get headers for Supabase REST API calls."""
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


@router.get(
    "/reasons",
    response_model=DeclineReasonsListResponse,
    summary="Get decline reasons",
)
async def get_decline_reasons(
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get available offer decline reason codes."""
    return DeclineReasonsListResponse(reasons=STANDARD_DECLINE_REASONS)


@router.post(
    "",
    response_model=OfferDeclineReasonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record decline reason",
)
async def record_decline_reason(
    request: OfferDeclineReasonCreate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Record why an offer was declined."""
    now = datetime.now(timezone.utc).isoformat()

    # Validate reason code
    valid_codes = {r.code for r in STANDARD_DECLINE_REASONS}
    if request.reason_code not in valid_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid reason code. Valid codes: {', '.join(valid_codes)}",
        )

    if request.secondary_reason_code and request.secondary_reason_code not in valid_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid secondary reason code",
        )

    async with httpx.AsyncClient() as client:
        # Verify offer exists and is in declined status
        offer_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status",
            },
            timeout=15,
        )

        if offer_response.status_code != 200 or not offer_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        offer_data = offer_response.json()[0]

        if offer_data["status"] != "declined":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only record decline reasons for declined offers",
            )

        # Check if decline reason already recorded
        existing_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            params={
                "offer_id": f"eq.{request.offer_id}",
                "select": "id",
            },
            timeout=15,
        )

        if existing_response.status_code == 200 and existing_response.json():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decline reason already recorded for this offer",
            )

        # Get reason details
        reason = next((r for r in STANDARD_DECLINE_REASONS if r.code == request.reason_code), None)

        decline_data = {
            "id": str(uuid4()),
            "tenant_id": str(current_user.tenant_id),
            "offer_id": str(request.offer_id),
            "reason_code": request.reason_code,
            "secondary_reason_code": request.secondary_reason_code,
            "notes": request.notes,
            "competing_company": request.competing_company,
            "competing_salary": request.competing_salary,
            "would_consider_future": request.would_consider_future,
            "follow_up_date": request.follow_up_date,
            "recorded_by": str(current_user.user_id),
            "created_at": now,
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            json=decline_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record decline reason: {response.text}",
            )

        result = response.json()[0]

        # Add derived fields
        result["reason_label"] = reason.label if reason else None
        result["reason_category"] = reason.category if reason else None

        return OfferDeclineReasonResponse(**result)


@router.get(
    "",
    response_model=List[OfferDeclineReasonResponse],
    summary="List decline reasons",
)
async def list_decline_reasons(
    reason_code: Optional[str] = None,
    category: Optional[str] = None,
    would_consider_future: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List recorded offer decline reasons."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }

        if reason_code:
            params["reason_code"] = f"eq.{reason_code}"
        if would_consider_future is not None:
            params["would_consider_future"] = f"eq.{str(would_consider_future).lower()}"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch decline reasons",
            )

        results = response.json()

        # Add derived fields and filter by category if needed
        reasons_map = {r.code: r for r in STANDARD_DECLINE_REASONS}
        enriched = []

        for result in results:
            reason = reasons_map.get(result["reason_code"])
            result["reason_label"] = reason.label if reason else None
            result["reason_category"] = reason.category if reason else None

            # Filter by category if specified
            if category:
                if result["reason_category"] == category:
                    enriched.append(OfferDeclineReasonResponse(**result))
            else:
                enriched.append(OfferDeclineReasonResponse(**result))

        return enriched


@router.get(
    "/{offer_id}",
    response_model=OfferDeclineReasonResponse,
    summary="Get decline reason for offer",
)
async def get_decline_reason(
    offer_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get the decline reason for a specific offer."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            params={
                "offer_id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Decline reason not found for this offer",
            )

        result = response.json()[0]

        # Add derived fields
        reason = next(
            (r for r in STANDARD_DECLINE_REASONS if r.code == result["reason_code"]),
            None
        )
        result["reason_label"] = reason.label if reason else None
        result["reason_category"] = reason.category if reason else None

        return OfferDeclineReasonResponse(**result)


@router.get(
    "/analytics/summary",
    response_model=DeclineAnalytics,
    summary="Get decline analytics",
)
async def get_decline_analytics(
    start_date: Optional[str] = Query(None, description="ISO date"),
    end_date: Optional[str] = Query(None, description="ISO date"),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get analytics on offer decline reasons."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
        }

        if start_date:
            params["created_at"] = f"gte.{start_date}"
        if end_date:
            params["created_at"] = f"and(created_at.lte.{end_date})"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch analytics",
            )

        declines = response.json()

        # Calculate analytics
        now = datetime.now(timezone.utc)
        analytics = DeclineAnalytics(
            period_start=datetime.fromisoformat(start_date) if start_date else now,
            period_end=datetime.fromisoformat(end_date) if end_date else now,
            total_declines=len(declines),
        )

        # Count by reason code
        reasons_map = {r.code: r for r in STANDARD_DECLINE_REASONS}
        reason_counts: dict = {}
        category_counts: dict = {}
        companies: dict = {}
        salary_diffs: list = []
        future_count = 0

        for d in declines:
            code = d["reason_code"]
            reason_counts[code] = reason_counts.get(code, 0) + 1

            reason = reasons_map.get(code)
            if reason:
                cat = reason.category
                category_counts[cat] = category_counts.get(cat, 0) + 1

            if d.get("competing_company"):
                company = d["competing_company"]
                companies[company] = companies.get(company, 0) + 1

            if d.get("competing_salary"):
                # Would need to get original offer salary to calculate diff
                salary_diffs.append(d["competing_salary"])

            if d.get("would_consider_future"):
                future_count += 1

        analytics.by_reason = reason_counts
        analytics.by_category = category_counts

        # Top reasons
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        analytics.top_reasons = [
            {
                "code": code,
                "label": reasons_map[code].label if code in reasons_map else code,
                "count": count,
                "percentage": round(count / len(declines) * 100, 1) if declines else 0,
            }
            for code, count in sorted_reasons[:10]
        ]

        # Competing companies
        sorted_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)
        analytics.competing_companies = [
            {"company": company, "count": count}
            for company, count in sorted_companies[:10]
        ]

        # Future consideration rate
        if declines:
            analytics.future_consideration_rate = round(future_count / len(declines) * 100, 1)

        return analytics


@router.get(
    "/re-engagement/candidates",
    summary="Get candidates open to future contact",
)
async def get_reengagement_candidates(
    limit: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get candidates who declined but indicated interest in future opportunities."""
    async with httpx.AsyncClient() as client:
        # Get decline reasons where candidate would consider future
        decline_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offer_decline_reasons",
            headers=_get_headers(),
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "would_consider_future": "eq.true",
                "select": "offer_id,reason_code,notes,follow_up_date,created_at",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=15,
        )

        if decline_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch re-engagement candidates",
            )

        declines = decline_response.json()

        if not declines:
            return {"candidates": [], "total": 0}

        # Get offer and candidate details
        offer_ids = [d["offer_id"] for d in declines]

        offers_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"in.({','.join(offer_ids)})",
                "select": "id,candidate_id,position_title",
            },
            timeout=15,
        )

        offers_map = {o["id"]: o for o in offers_response.json()} if offers_response.json() else {}

        # Get candidate details
        candidate_ids = list(set(o["candidate_id"] for o in offers_map.values()))

        if candidate_ids:
            candidates_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"in.({','.join(candidate_ids)})",
                    "select": "id,first_name,last_name,email",
                },
                timeout=15,
            )

            candidates_map = {c["id"]: c for c in candidates_response.json()} if candidates_response.json() else {}
        else:
            candidates_map = {}

        # Build results
        results = []
        for d in declines:
            offer = offers_map.get(d["offer_id"], {})
            candidate = candidates_map.get(offer.get("candidate_id"), {})

            results.append({
                "candidate_id": offer.get("candidate_id"),
                "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
                "email": candidate.get("email"),
                "position_declined": offer.get("position_title"),
                "decline_reason": d["reason_code"],
                "decline_notes": d.get("notes"),
                "declined_at": d["created_at"],
                "follow_up_date": d.get("follow_up_date"),
            })

        return {"candidates": results, "total": len(results)}
