"""Red Flags router for candidate risk management."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.red_flag import (
    RedFlagCreate,
    RedFlagUpdate,
    RedFlagResponse,
    RedFlagSummary,
    RedFlagTypesResponse,
    STANDARD_RED_FLAG_TYPES,
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
    "/types",
    response_model=RedFlagTypesResponse,
    summary="Get red flag types",
)
async def get_red_flag_types(
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get available red flag types."""
    return RedFlagTypesResponse(types=STANDARD_RED_FLAG_TYPES)


@router.post(
    "",
    response_model=RedFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add red flag",
)
async def create_red_flag(
    request: RedFlagCreate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Add a red flag to a candidate."""
    now = datetime.now(timezone.utc).isoformat()

    # Validate flag type
    valid_types = {t.code for t in STANDARD_RED_FLAG_TYPES}
    if request.flag_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid flag type. Valid types: {', '.join(valid_types)}",
        )

    # Validate severity
    if request.severity not in ["low", "medium", "high"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Severity must be 'low', 'medium', or 'high'",
        )

    async with httpx.AsyncClient() as client:
        # Verify candidate exists
        candidate_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidates",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.candidate_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id",
            },
            timeout=15,
        )

        if candidate_response.status_code != 200 or not candidate_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )

        flag_data = {
            "id": str(uuid4()),
            "tenant_id": str(current_user.tenant_id),
            "candidate_id": str(request.candidate_id),
            "flag_type": request.flag_type,
            "severity": request.severity,
            "reason": request.reason,
            "is_blocking": request.is_blocking,
            "is_resolved": False,
            "expiration_date": request.expiration_date,
            "created_by": str(current_user.user_id),
            "created_at": now,
            "updated_at": now,
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            json=flag_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create red flag: {response.text}",
            )

        return RedFlagResponse(**response.json()[0])


@router.get(
    "",
    response_model=List[RedFlagResponse],
    summary="List red flags",
)
async def list_red_flags(
    candidate_id: Optional[UUID] = None,
    flag_type: Optional[str] = None,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    is_blocking: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """List red flags with optional filters."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }

        if candidate_id:
            params["candidate_id"] = f"eq.{candidate_id}"
        if flag_type:
            params["flag_type"] = f"eq.{flag_type}"
        if severity:
            params["severity"] = f"eq.{severity}"
        if is_resolved is not None:
            params["is_resolved"] = f"eq.{str(is_resolved).lower()}"
        if is_blocking is not None:
            params["is_blocking"] = f"eq.{str(is_blocking).lower()}"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch red flags",
            )

        flags = response.json()

        # Enrich with creator names
        creator_ids = list(set(f["created_by"] for f in flags))
        if creator_ids:
            users_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"in.({','.join(creator_ids)})",
                    "select": "id,full_name",
                },
                timeout=15,
            )

            if users_response.status_code == 200:
                users_map = {u["id"]: u.get("full_name") for u in users_response.json()}
                for flag in flags:
                    flag["created_by_name"] = users_map.get(flag["created_by"])
                    if flag.get("resolved_by"):
                        flag["resolved_by_name"] = users_map.get(flag["resolved_by"])

        return [RedFlagResponse(**f) for f in flags]


@router.get(
    "/summary/{candidate_id}",
    response_model=RedFlagSummary,
    summary="Get flag summary for candidate",
)
async def get_candidate_flag_summary(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get summary of all flags for a candidate."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "candidate_id": f"eq.{candidate_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
                "order": "created_at.desc",
            },
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch flags",
            )

        flags = response.json()

        summary = RedFlagSummary(
            candidate_id=candidate_id,
            total_flags=len(flags),
            flags=[RedFlagResponse(**f) for f in flags],
        )

        # Calculate counts
        for flag in flags:
            if flag.get("is_resolved"):
                summary.resolved_flags += 1
            else:
                summary.active_flags += 1
                if flag.get("is_blocking"):
                    summary.blocking_flags += 1

                severity = flag.get("severity", "low")
                if severity == "high":
                    summary.high_severity_count += 1
                elif severity == "medium":
                    summary.medium_severity_count += 1
                else:
                    summary.low_severity_count += 1

        # Determine overall status
        summary.has_blocking = summary.blocking_flags > 0

        if summary.high_severity_count > 0:
            summary.most_severe = "high"
        elif summary.medium_severity_count > 0:
            summary.most_severe = "medium"
        elif summary.low_severity_count > 0:
            summary.most_severe = "low"

        return summary


@router.get(
    "/{flag_id}",
    response_model=RedFlagResponse,
    summary="Get red flag",
)
async def get_red_flag(
    flag_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Get a specific red flag."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "id": f"eq.{flag_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Red flag not found",
            )

        return RedFlagResponse(**response.json()[0])


@router.patch(
    "/{flag_id}",
    response_model=RedFlagResponse,
    summary="Update red flag",
)
async def update_red_flag(
    flag_id: UUID,
    request: RedFlagUpdate,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Update a red flag."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify flag exists
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "id": f"eq.{flag_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Red flag not found",
            )

        update_data = {"updated_at": now}

        if request.severity is not None:
            if request.severity not in ["low", "medium", "high"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Severity must be 'low', 'medium', or 'high'",
                )
            update_data["severity"] = request.severity

        if request.reason is not None:
            update_data["reason"] = request.reason

        if request.is_blocking is not None:
            update_data["is_blocking"] = request.is_blocking

        if request.expiration_date is not None:
            update_data["expiration_date"] = request.expiration_date

        if request.is_resolved is not None:
            update_data["is_resolved"] = request.is_resolved
            if request.is_resolved:
                update_data["resolved_at"] = now
                update_data["resolved_by"] = str(current_user.user_id)
                if request.resolution_notes:
                    update_data["resolution_notes"] = request.resolution_notes

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={"id": f"eq.{flag_id}"},
            json=update_data,
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update red flag",
            )

        # Fetch and return updated
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={"id": f"eq.{flag_id}", "select": "*"},
            timeout=15,
        )

        return RedFlagResponse(**get_response.json()[0])


@router.post(
    "/{flag_id}/resolve",
    response_model=RedFlagResponse,
    summary="Resolve red flag",
)
async def resolve_red_flag(
    flag_id: UUID,
    resolution_notes: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_EDIT)),
):
    """Mark a red flag as resolved."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify flag exists and is not already resolved
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "id": f"eq.{flag_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,is_resolved",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Red flag not found",
            )

        if check_response.json()[0].get("is_resolved"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Red flag is already resolved",
            )

        response = await client.patch(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={"id": f"eq.{flag_id}"},
            json={
                "is_resolved": True,
                "resolved_at": now,
                "resolved_by": str(current_user.user_id),
                "resolution_notes": resolution_notes,
                "updated_at": now,
            },
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resolve red flag",
            )

        # Fetch and return updated
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={"id": f"eq.{flag_id}", "select": "*"},
            timeout=15,
        )

        return RedFlagResponse(**get_response.json()[0])


@router.delete(
    "/{flag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete red flag",
)
async def delete_red_flag(
    flag_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_DELETE)),
):
    """Delete a red flag (admin only)."""
    async with httpx.AsyncClient() as client:
        # Verify flag exists
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "id": f"eq.{flag_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Red flag not found",
            )

        response = await client.delete(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={"id": f"eq.{flag_id}"},
            timeout=15,
        )

        if response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete red flag",
            )


@router.get(
    "/check/{candidate_id}",
    summary="Check for blocking flags",
)
async def check_blocking_flags(
    candidate_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.CANDIDATES_VIEW)),
):
    """Quick check if candidate has any blocking flags (used before advancing)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/candidate_red_flags",
            headers=_get_headers(),
            params={
                "candidate_id": f"eq.{candidate_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "is_blocking": "eq.true",
                "is_resolved": "eq.false",
                "select": "id,flag_type,severity,reason",
            },
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check flags",
            )

        blocking_flags = response.json()

        return {
            "has_blocking_flags": len(blocking_flags) > 0,
            "blocking_count": len(blocking_flags),
            "blocking_flags": blocking_flags,
            "can_advance": len(blocking_flags) == 0,
        }
