"""Reports router for recruiting analytics and dashboards."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.permissions import Permission, require_permission
from app.core.security import TokenData
from app.recruiting.services.analytics_service import get_analytics_service


router = APIRouter()


@router.get(
    "/dashboard",
    summary="Get dashboard summary",
)
async def get_dashboard_summary(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get high-level dashboard summary metrics."""
    analytics = get_analytics_service()
    return await analytics.get_dashboard_summary(current_user.tenant_id)


@router.get(
    "/recruiter-performance",
    summary="Get recruiter performance metrics",
)
async def get_recruiter_performance(
    recruiter_id: Optional[UUID] = None,
    start_date: Optional[str] = Query(None, description="ISO format date"),
    end_date: Optional[str] = Query(None, description="ISO format date"),
    current_user: TokenData = Depends(require_permission(Permission.WORKLOAD_VIEW)),
):
    """Get recruiter performance metrics.

    Includes jobs filled, time-to-fill averages, applications processed,
    and offer acceptance rates.
    """
    analytics = get_analytics_service()
    return await analytics.get_recruiter_performance(
        tenant_id=current_user.tenant_id,
        recruiter_id=recruiter_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/time-to-fill",
    summary="Get time-to-fill report",
)
async def get_time_to_fill(
    start_date: Optional[str] = Query(None, description="ISO format date"),
    end_date: Optional[str] = Query(None, description="ISO format date"),
    department: Optional[str] = None,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get time-to-fill analytics.

    Shows average, min, max, and median days to fill positions,
    broken down by department.
    """
    analytics = get_analytics_service()
    return await analytics.get_time_to_fill_report(
        tenant_id=current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
        department=department,
    )


@router.get(
    "/source-effectiveness",
    summary="Get source effectiveness report",
)
async def get_source_effectiveness(
    start_date: Optional[str] = Query(None, description="ISO format date"),
    end_date: Optional[str] = Query(None, description="ISO format date"),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get application source effectiveness metrics.

    Shows which sources (job boards, referrals, etc.) produce
    the highest quality candidates based on hire rates.
    """
    analytics = get_analytics_service()
    return await analytics.get_source_effectiveness_report(
        tenant_id=current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/pipeline-funnel",
    summary="Get pipeline funnel report",
)
async def get_pipeline_funnel(
    requisition_id: Optional[UUID] = None,
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get pipeline funnel analytics.

    Shows candidate progression through stages with conversion rates
    at each step. Can be filtered to a specific job.
    """
    analytics = get_analytics_service()
    return await analytics.get_pipeline_funnel_report(
        tenant_id=current_user.tenant_id,
        requisition_id=requisition_id,
    )


@router.get(
    "/sla-overview",
    summary="Get SLA overview",
)
async def get_sla_overview(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get overview of SLA compliance.

    Shows jobs and assignments at risk of missing SLA deadlines.
    """
    from app.config import get_settings
    import httpx

    settings = get_settings()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # Get unacknowledged alerts
        alerts_response = await client.get(
            f"{settings.supabase_url}/rest/v1/sla_alerts",
            headers=headers,
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "acknowledged_at": "is.null",
                "select": "*",
                "order": "triggered_at.desc",
            },
            timeout=15,
        )

        alerts = alerts_response.json() if alerts_response.status_code == 200 else []

        # Count by type
        amber_count = len([a for a in alerts if a.get("alert_type") == "amber"])
        red_count = len([a for a in alerts if a.get("alert_type") == "red"])

        # Get jobs with SLA data
        jobs_response = await client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=headers,
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "status": "eq.open",
                "job_sla_deadline": "not.is.null",
                "select": "id,title,job_sla_deadline,job_opened_at",
                "order": "job_sla_deadline.asc",
                "limit": "20",
            },
            timeout=15,
        )

        jobs_at_risk = jobs_response.json() if jobs_response.status_code == 200 else []

        return {
            "alerts": {
                "amber": amber_count,
                "red": red_count,
                "total": len(alerts),
            },
            "recent_alerts": alerts[:10],
            "jobs_approaching_deadline": jobs_at_risk,
        }


@router.get(
    "/hiring-velocity",
    summary="Get hiring velocity trends",
)
async def get_hiring_velocity(
    period: str = Query("month", pattern="^(week|month|quarter)$"),
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get hiring velocity trends.

    Shows hires per period over time to identify trends.
    """
    from datetime import datetime, timedelta, timezone
    from app.config import get_settings
    import httpx

    settings = get_settings()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    # Determine time range
    now = datetime.now(timezone.utc)
    if period == "week":
        periods = 12  # Last 12 weeks
        delta = timedelta(weeks=1)
    elif period == "month":
        periods = 12  # Last 12 months
        delta = timedelta(days=30)
    else:  # quarter
        periods = 8  # Last 8 quarters
        delta = timedelta(days=90)

    # Get all hires in the time range
    start_date = now - (delta * periods)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=headers,
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "status": "eq.hired",
                "hired_at": f"gte.{start_date.isoformat()}",
                "select": "id,hired_at",
            },
            timeout=30,
        )

        hires = response.json() if response.status_code == 200 else []

        # Group by period
        velocity_data = []
        for i in range(periods):
            period_start = now - (delta * (i + 1))
            period_end = now - (delta * i)

            period_hires = [
                h for h in hires
                if h.get("hired_at") and
                period_start.isoformat() <= h["hired_at"] < period_end.isoformat()
            ]

            velocity_data.append({
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "hires": len(period_hires),
            })

        # Reverse to show oldest first
        velocity_data.reverse()

        return {
            "period_type": period,
            "data": velocity_data,
            "total_hires": len(hires),
            "average_per_period": round(len(hires) / periods, 1) if periods > 0 else 0,
        }


@router.get(
    "/department-breakdown",
    summary="Get department breakdown",
)
async def get_department_breakdown(
    current_user: TokenData = Depends(require_permission(Permission.JOBS_VIEW)),
):
    """Get recruiting metrics broken down by department."""
    from app.config import get_settings
    import httpx

    settings = get_settings()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # Get jobs by department
        jobs_response = await client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=headers,
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,department,status",
            },
            timeout=30,
        )

        jobs = jobs_response.json() if jobs_response.status_code == 200 else []

        # Get applications
        apps_response = await client.get(
            f"{settings.supabase_url}/rest/v1/applications",
            headers=headers,
            params={
                "tenant_id": f"eq.{current_user.tenant_id}",
                "select": "id,requisition_id,status",
            },
            timeout=30,
        )

        applications = apps_response.json() if apps_response.status_code == 200 else []

        # Build job -> department mapping
        job_dept_map = {j["id"]: j.get("department", "Unknown") for j in jobs}

        # Group metrics by department
        departments = {}
        for job in jobs:
            dept = job.get("department") or "Unknown"
            if dept not in departments:
                departments[dept] = {
                    "department": dept,
                    "open_jobs": 0,
                    "filled_jobs": 0,
                    "total_applications": 0,
                    "hired": 0,
                }

            if job.get("status") == "open":
                departments[dept]["open_jobs"] += 1
            elif job.get("status") in ("filled", "closed"):
                departments[dept]["filled_jobs"] += 1

        # Add application counts
        for app in applications:
            req_id = app.get("requisition_id")
            dept = job_dept_map.get(req_id, "Unknown")

            if dept not in departments:
                departments[dept] = {
                    "department": dept,
                    "open_jobs": 0,
                    "filled_jobs": 0,
                    "total_applications": 0,
                    "hired": 0,
                }

            departments[dept]["total_applications"] += 1
            if app.get("status") == "hired":
                departments[dept]["hired"] += 1

        # Sort by total applications
        dept_list = sorted(
            departments.values(),
            key=lambda x: x["total_applications"],
            reverse=True
        )

        return {
            "departments": dept_list,
            "total_departments": len(dept_list),
        }
