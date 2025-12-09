"""Bulk operations router for recruiting applications."""

from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.schemas.bulk import (
    BulkStageChangeRequest,
    BulkStageChangeResponse,
    BulkRejectRequest,
    BulkRejectResponse,
    BulkTagRequest,
    BulkTagResponse,
    BulkAssignRequest,
    BulkAssignResponse,
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


@router.post(
    "/stage",
    response_model=BulkStageChangeResponse,
    summary="Bulk change application stages",
)
async def bulk_stage_change(
    request: BulkStageChangeRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_MOVE_STAGE)),
):
    """Change the stage for multiple applications at once."""
    result = BulkStageChangeResponse(
        success_count=0,
        failure_count=0,
        failed_ids=[],
        errors=[],
    )

    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        for app_id in request.application_ids:
            try:
                # First verify application exists and belongs to tenant
                check_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{app_id}",
                        "tenant_id": f"eq.{current_user.tenant_id}",
                        "select": "id,current_stage",
                    },
                    timeout=15,
                )

                if check_response.status_code != 200 or not check_response.json():
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    result.errors.append(f"Application {app_id} not found")
                    continue

                old_stage = check_response.json()[0].get("current_stage")

                # Update application stage
                update_data = {
                    "current_stage": request.target_stage,
                    "updated_at": now,
                }

                update_response = await client.patch(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={"id": f"eq.{app_id}"},
                    json=update_data,
                    timeout=15,
                )

                if update_response.status_code in (200, 204):
                    result.success_count += 1

                    # Create stage history entry
                    history_data = {
                        "tenant_id": str(current_user.tenant_id),
                        "application_id": str(app_id),
                        "from_stage": old_stage,
                        "to_stage": request.target_stage,
                        "changed_by": str(current_user.sub),
                        "notes": request.notes or f"Bulk stage change to {request.target_stage}",
                        "created_at": now,
                    }

                    await client.post(
                        f"{settings.supabase_url}/rest/v1/application_stage_history",
                        headers=_get_headers(),
                        json=history_data,
                        timeout=15,
                    )
                else:
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    result.errors.append(f"Failed to update {app_id}")

            except Exception as e:
                result.failure_count += 1
                result.failed_ids.append(app_id)
                result.errors.append(str(e))

    return result


@router.post(
    "/reject",
    response_model=BulkRejectResponse,
    summary="Bulk reject applications",
)
async def bulk_reject(
    request: BulkRejectRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_REJECT)),
):
    """Reject multiple applications at once."""
    result = BulkRejectResponse(
        rejected_count=0,
        failure_count=0,
        failed_ids=[],
        errors=[],
    )

    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        for app_id in request.application_ids:
            try:
                # Verify application exists
                check_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{app_id}",
                        "tenant_id": f"eq.{current_user.tenant_id}",
                        "select": "id,current_stage,status",
                    },
                    timeout=15,
                )

                if check_response.status_code != 200 or not check_response.json():
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    result.errors.append(f"Application {app_id} not found")
                    continue

                app_data = check_response.json()[0]

                # Skip already rejected
                if app_data.get("status") == "rejected":
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    result.errors.append(f"Application {app_id} already rejected")
                    continue

                # Update application
                update_data = {
                    "status": "rejected",
                    "current_stage": "rejected",
                    "rejection_reason": request.rejection_reason,
                    "rejection_notes": request.notes,
                    "rejected_at": now,
                    "rejected_by": str(current_user.sub),
                    "updated_at": now,
                }

                if request.rejection_reason_id:
                    update_data["disposition_reason_id"] = str(request.rejection_reason_id)

                update_response = await client.patch(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={"id": f"eq.{app_id}"},
                    json=update_data,
                    timeout=15,
                )

                if update_response.status_code in (200, 204):
                    result.rejected_count += 1

                    # Create stage history entry
                    history_data = {
                        "tenant_id": str(current_user.tenant_id),
                        "application_id": str(app_id),
                        "from_stage": app_data.get("current_stage"),
                        "to_stage": "rejected",
                        "changed_by": str(current_user.sub),
                        "notes": request.notes or "Bulk rejection",
                        "created_at": now,
                    }

                    await client.post(
                        f"{settings.supabase_url}/rest/v1/application_stage_history",
                        headers=_get_headers(),
                        json=history_data,
                        timeout=15,
                    )
                else:
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    result.errors.append(f"Failed to reject {app_id}")

            except Exception as e:
                result.failure_count += 1
                result.failed_ids.append(app_id)
                result.errors.append(str(e))

    return result


@router.post(
    "/tags",
    response_model=BulkTagResponse,
    summary="Bulk add/remove tags",
)
async def bulk_tags(
    request: BulkTagRequest,
    current_user: TokenData = Depends(require_permission(Permission.APPLICATIONS_EDIT)),
):
    """Add or remove tags from multiple applications."""
    result = BulkTagResponse(
        updated_count=0,
        failure_count=0,
        failed_ids=[],
    )

    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        for app_id in request.application_ids:
            try:
                # Get current application
                get_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{app_id}",
                        "tenant_id": f"eq.{current_user.tenant_id}",
                        "select": "id,tags",
                    },
                    timeout=15,
                )

                if get_response.status_code != 200 or not get_response.json():
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    continue

                current_tags = get_response.json()[0].get("tags") or []

                if request.action == "add":
                    new_tags = list(set(current_tags + request.tags))
                else:  # remove
                    new_tags = [t for t in current_tags if t not in request.tags]

                # Update tags
                update_response = await client.patch(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={"id": f"eq.{app_id}"},
                    json={"tags": new_tags, "updated_at": now},
                    timeout=15,
                )

                if update_response.status_code in (200, 204):
                    result.updated_count += 1
                else:
                    result.failure_count += 1
                    result.failed_ids.append(app_id)

            except Exception as e:
                result.failure_count += 1
                result.failed_ids.append(app_id)

    return result


@router.post(
    "/assign",
    response_model=BulkAssignResponse,
    summary="Bulk assign applications",
)
async def bulk_assign(
    request: BulkAssignRequest,
    current_user: TokenData = Depends(require_permission(Permission.WORKLOAD_ASSIGN)),
):
    """Assign multiple applications to a recruiter."""
    result = BulkAssignResponse(
        assigned_count=0,
        failure_count=0,
        failed_ids=[],
    )

    now = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        for app_id in request.application_ids:
            try:
                # Verify application exists
                check_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{app_id}",
                        "tenant_id": f"eq.{current_user.tenant_id}",
                        "select": "id",
                    },
                    timeout=15,
                )

                if check_response.status_code != 200 or not check_response.json():
                    result.failure_count += 1
                    result.failed_ids.append(app_id)
                    continue

                # Update assignee
                update_response = await client.patch(
                    f"{settings.supabase_url}/rest/v1/applications",
                    headers=_get_headers(),
                    params={"id": f"eq.{app_id}"},
                    json={
                        "assigned_to": str(request.assignee_id),
                        "assigned_at": now,
                        "updated_at": now,
                    },
                    timeout=15,
                )

                if update_response.status_code in (200, 204):
                    result.assigned_count += 1
                else:
                    result.failure_count += 1
                    result.failed_ids.append(app_id)

            except Exception as e:
                result.failure_count += 1
                result.failed_ids.append(app_id)

    return result
