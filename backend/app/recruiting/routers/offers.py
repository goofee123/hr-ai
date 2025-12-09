"""Offers router for recruiting."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.bulk import (
    OfferCreate,
    OfferUpdate,
    OfferResponse,
    OfferApprovalRequest,
    OfferSendRequest,
    OfferCandidateActionRequest,
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


def _calculate_total_compensation(base_salary: float, bonus_percent: Optional[float]) -> float:
    """Calculate total annual compensation."""
    bonus = (base_salary * (bonus_percent / 100)) if bonus_percent else 0
    return base_salary + bonus


@router.post(
    "",
    response_model=OfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an offer",
)
async def create_offer(
    request: OfferCreate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Create a new job offer for an application."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify application exists and get details
        app_response = await client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=_get_headers(),
            params={
                "id": f"eq.{request.application_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,candidate_id,requisition_id",
            },
            timeout=15,
        )

        if app_response.status_code != 200 or not app_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

        app_data = app_response.json()[0]

        # Create offer
        offer_data = {
            "tenant_id": str(current_user.tenant_id),
            "application_id": str(request.application_id),
            "candidate_id": app_data["candidate_id"],
            "requisition_id": app_data["requisition_id"],
            "position_title": request.position_title,
            "department": request.department,
            "base_salary": request.base_salary,
            "currency": request.currency,
            "bonus_percent": request.bonus_percent,
            "equity_shares": request.equity_shares,
            "total_compensation": _calculate_total_compensation(
                request.base_salary, request.bonus_percent
            ),
            "start_date": request.start_date,
            "expiration_date": request.expiration_date,
            "status": "draft",
            "notes": request.notes,
            "created_by": str(current_user.sub),
            "created_at": now,
            "updated_at": now,
        }

        create_response = await client.post(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            json=offer_data,
            timeout=15,
        )

        if create_response.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create offer: {create_response.text}",
            )

        created_offer = create_response.json()[0]

        return OfferResponse(**created_offer)


@router.get(
    "",
    summary="List offers",
)
async def list_offers(
    requisition_id: Optional[UUID] = None,
    candidate_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """List offers with optional filters."""
    async with httpx.AsyncClient() as client:
        params = {
            "tenant_id": f"eq.{current_user.tenant_id}",
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }

        if requisition_id:
            params["requisition_id"] = f"eq.{requisition_id}"
        if candidate_id:
            params["candidate_id"] = f"eq.{candidate_id}"
        if status_filter:
            params["status"] = f"eq.{status_filter}"

        response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers={**_get_headers(), "Prefer": "count=exact"},
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch offers",
            )

        total = 0
        if "content-range" in response.headers:
            range_header = response.headers["content-range"]
            if "/" in range_header:
                total = int(range_header.split("/")[1])

        return {
            "offers": response.json(),
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get(
    "/{offer_id}",
    response_model=OfferResponse,
    summary="Get offer details",
)
async def get_offer(
    offer_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_VIEW)),
):
    """Get details of a specific offer."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if response.status_code != 200 or not response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        return OfferResponse(**response.json()[0])


@router.patch(
    "/{offer_id}",
    response_model=OfferResponse,
    summary="Update offer",
)
async def update_offer(
    offer_id: UUID,
    request: OfferUpdate,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Update an offer (only if in draft status)."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify offer exists and is in draft
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "*",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        existing = check_response.json()[0]

        if existing["status"] not in ("draft", "pending_approval"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only update offers in draft or pending_approval status",
            )

        # Build update data
        update_data = {"updated_at": now}
        for field in ["position_title", "department", "base_salary", "currency",
                      "bonus_percent", "equity_shares", "start_date", "expiration_date", "notes"]:
            value = getattr(request, field)
            if value is not None:
                update_data[field] = value

        # Recalculate total compensation if salary or bonus changed
        base = update_data.get("base_salary", existing["base_salary"])
        bonus = update_data.get("bonus_percent", existing.get("bonus_percent"))
        update_data["total_compensation"] = _calculate_total_compensation(base, bonus)

        update_response = await client.patch(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            json=update_data,
            timeout=15,
        )

        if update_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update offer",
            )

        # Fetch updated offer
        get_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}", "select": "*"},
            timeout=15,
        )

        return OfferResponse(**get_response.json()[0])


@router.post(
    "/{offer_id}/submit",
    summary="Submit offer for approval",
)
async def submit_for_approval(
    offer_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Submit an offer for approval."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify offer is in draft
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        if check_response.json()[0]["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft offers can be submitted for approval",
            )

        # Update status
        update_response = await client.patch(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            json={
                "status": "pending_approval",
                "submitted_at": now,
                "submitted_by": str(current_user.sub),
                "updated_at": now,
            },
            timeout=15,
        )

        if update_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to submit offer",
            )

        return {"message": "Offer submitted for approval", "offer_id": str(offer_id)}


@router.post(
    "/{offer_id}/approval",
    summary="Approve or reject offer",
)
async def handle_approval(
    offer_id: UUID,
    request: OfferApprovalRequest,
    current_user: TokenData = Depends(require_permission(Permission.WORKSHEET_APPROVE)),
):
    """Approve or reject an offer (requires approval permission)."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify offer is pending approval
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        if check_response.json()[0]["status"] != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only offers pending approval can be approved/rejected",
            )

        new_status = "approved" if request.action == "approve" else "rejected"

        update_response = await client.patch(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            json={
                "status": new_status,
                "approved_by": str(current_user.sub),
                "approved_at": now,
                "approval_notes": request.notes,
                "updated_at": now,
            },
            timeout=15,
        )

        if update_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update offer",
            )

        return {
            "message": f"Offer {request.action}d",
            "offer_id": str(offer_id),
            "status": new_status,
        }


@router.post(
    "/{offer_id}/send",
    summary="Send offer to candidate",
)
async def send_offer(
    offer_id: UUID,
    request: OfferSendRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Send an approved offer to the candidate."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify offer is approved
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status,candidate_id",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        offer_data = check_response.json()[0]

        if offer_data["status"] != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only approved offers can be sent",
            )

        # Update status to sent
        update_response = await client.patch(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            json={
                "status": "sent",
                "sent_at": now,
                "sent_by": str(current_user.sub),
                "updated_at": now,
            },
            timeout=15,
        )

        if update_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update offer",
            )

        # TODO: Send email notification if request.send_email is True

        return {
            "message": "Offer sent to candidate",
            "offer_id": str(offer_id),
            "email_sent": request.send_email,
        }


@router.post(
    "/{offer_id}/candidate-action",
    summary="Record candidate response",
)
async def record_candidate_action(
    offer_id: UUID,
    request: OfferCandidateActionRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Record candidate's response to an offer."""
    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Verify offer is sent
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status,application_id",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        offer_data = check_response.json()[0]

        if offer_data["status"] != "sent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only record response for sent offers",
            )

        status_map = {
            "accept": "accepted",
            "decline": "declined",
            "negotiate": "negotiating",
        }

        new_status = status_map[request.action]

        update_data = {
            "status": new_status,
            "candidate_responded_at": now,
            "updated_at": now,
        }

        if request.action == "negotiate":
            update_data["negotiation_notes"] = request.negotiation_notes
            update_data["counter_offer_salary"] = request.counter_offer_salary

        update_response = await client.patch(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            json=update_data,
            timeout=15,
        )

        if update_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update offer",
            )

        # If accepted, update application status to hired
        if request.action == "accept":
            await client.patch(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={"id": f"eq.{offer_data['application_id']}"},
                json={
                    "status": "hired",
                    "current_stage": "hired",
                    "hired_at": now,
                    "updated_at": now,
                },
                timeout=15,
            )

        return {
            "message": f"Offer {new_status}",
            "offer_id": str(offer_id),
            "status": new_status,
        }


@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete offer",
)
async def delete_offer(
    offer_id: UUID,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Delete an offer (only if in draft status)."""
    async with httpx.AsyncClient() as client:
        # Verify offer is in draft
        check_response = await client.get(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={
                "id": f"eq.{offer_id}",
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,status",
            },
            timeout=15,
        )

        if check_response.status_code != 200 or not check_response.json():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        if check_response.json()[0]["status"] != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft offers can be deleted",
            )

        delete_response = await client.delete(
            f"{settings.supabase_url}/rest/v1/offers",
            headers=_get_headers(),
            params={"id": f"eq.{offer_id}"},
            timeout=15,
        )

        if delete_response.status_code not in (200, 204):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete offer",
            )
