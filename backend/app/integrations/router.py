"""Integrations router for external system connections."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.integrations.dayforce import get_dayforce_sync_service


router = APIRouter()


class SyncJobsRequest(BaseModel):
    """Request to sync jobs from Dayforce."""

    force: bool = Field(False, description="Force full resync")


class SyncJobsResponse(BaseModel):
    """Response from job sync operation."""

    synced: int
    created: int
    updated: int
    errors: int
    error_details: list[str] = []


class SyncEmployeesResponse(BaseModel):
    """Response from employee sync operation."""

    synced: int
    created: int
    updated: int
    errors: int


class IntegrationStatus(BaseModel):
    """Status of an integration."""

    connected: bool
    jobs_synced: Optional[int] = None
    last_sync: Optional[str] = None
    dayforce_url: Optional[str] = None
    client_namespace: Optional[str] = None
    error: Optional[str] = None


class DayforceConfigUpdate(BaseModel):
    """Request to update Dayforce configuration."""

    base_url: Optional[str] = None
    client_namespace: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@router.post(
    "/dayforce/sync/jobs",
    response_model=SyncJobsResponse,
    summary="Sync jobs from Dayforce",
)
async def sync_dayforce_jobs(
    request: SyncJobsRequest = SyncJobsRequest(),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Sync job openings from Dayforce HCM to our system."""
    sync_service = get_dayforce_sync_service()

    result = await sync_service.sync_job_openings(current_user.tenant_id)

    return SyncJobsResponse(
        synced=result["synced"],
        created=result["created"],
        updated=result["updated"],
        errors=result["errors"],
        error_details=result.get("error_details", []),
    )


@router.post(
    "/dayforce/sync/employees",
    response_model=SyncEmployeesResponse,
    summary="Sync employees from Dayforce",
)
async def sync_dayforce_employees(
    current_user: TokenData = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Sync employees from Dayforce HCM for referral lookups."""
    sync_service = get_dayforce_sync_service()

    result = await sync_service.sync_employees(current_user.tenant_id)

    return SyncEmployeesResponse(
        synced=result["synced"],
        created=result["created"],
        updated=result["updated"],
        errors=result["errors"],
    )


@router.get(
    "/dayforce/status",
    response_model=IntegrationStatus,
    summary="Get Dayforce integration status",
)
async def get_dayforce_status(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get the status of the Dayforce integration."""
    sync_service = get_dayforce_sync_service()

    status_info = await sync_service.get_sync_status(current_user.tenant_id)

    return IntegrationStatus(**status_info)


@router.post(
    "/dayforce/test",
    summary="Test Dayforce connection",
)
async def test_dayforce_connection(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_EDIT)),
):
    """Test the connection to Dayforce HCM."""
    sync_service = get_dayforce_sync_service()

    # Try to authenticate
    success = await sync_service.client.authenticate()

    if success:
        return {
            "success": True,
            "message": "Successfully connected to Dayforce",
        }
    else:
        return {
            "success": False,
            "message": "Failed to connect to Dayforce. Check credentials.",
        }


@router.get(
    "/status",
    summary="Get all integrations status",
)
async def get_all_integrations_status(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get status of all external integrations."""
    sync_service = get_dayforce_sync_service()
    dayforce_status = await sync_service.get_sync_status(current_user.tenant_id)

    return {
        "integrations": {
            "dayforce": {
                "name": "Dayforce HCM",
                "status": "connected" if dayforce_status.get("connected") else "not_configured",
                "last_sync": dayforce_status.get("last_sync"),
                "jobs_synced": dayforce_status.get("jobs_synced", 0),
            },
            "linkedin": {
                "name": "LinkedIn Recruiter",
                "status": "not_configured",
                "last_sync": None,
            },
            "indeed": {
                "name": "Indeed",
                "status": "not_configured",
                "last_sync": None,
            },
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
