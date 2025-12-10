"""SLA Alert Scheduler - Background task to check and send SLA alerts."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from uuid import UUID

import httpx
from arq import cron

from app.config import get_settings
from app.services.email_service import get_email_service

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


async def check_sla_alerts(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to check all job openings and recruiter assignments for SLA breaches.

    This task should run periodically (e.g., every hour) to:
    1. Check job opening SLAs
    2. Check recruiter assignment SLAs
    3. Generate amber/red alerts as needed
    4. Send email notifications to affected recruiters

    Returns a summary of alerts generated.
    """
    logger.info("Starting SLA alert check...")

    now = datetime.now(timezone.utc)
    results = {
        "checked_at": now.isoformat(),
        "jobs_checked": 0,
        "assignments_checked": 0,
        "amber_alerts": 0,
        "red_alerts": 0,
        "emails_sent": 0,
        "errors": [],
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        # Get all SLA configurations (cached for batch processing)
        sla_configs = await _get_sla_configs(client)

        # Check job opening SLAs
        job_alerts = await _check_job_slas(client, sla_configs, now)
        results["jobs_checked"] = job_alerts["checked"]
        results["amber_alerts"] += job_alerts["amber"]
        results["red_alerts"] += job_alerts["red"]

        # Check recruiter assignment SLAs
        assignment_alerts = await _check_assignment_slas(client, sla_configs, now)
        results["assignments_checked"] = assignment_alerts["checked"]
        results["amber_alerts"] += assignment_alerts["amber"]
        results["red_alerts"] += assignment_alerts["red"]

        # Send email notifications for new alerts
        all_alerts = job_alerts["alerts"] + assignment_alerts["alerts"]
        for alert in all_alerts:
            try:
                if alert.get("recruiter_email"):
                    await email_service.send_sla_alert(
                        recruiter_email=alert["recruiter_email"],
                        recruiter_name=alert.get("recruiter_name", "Recruiter"),
                        alert_level=alert["level"],
                        job_title=alert["job_title"],
                        job_id=alert["job_id"],
                        days_remaining=alert["days_remaining"],
                        sla_days=alert["sla_days"],
                        candidates_in_pipeline=alert.get("candidates_count", 0),
                    )
                    results["emails_sent"] += 1
            except Exception as e:
                logger.error(f"Failed to send SLA alert email: {str(e)}")
                results["errors"].append(str(e))

    logger.info(f"SLA check complete: {results}")
    return results


async def _get_sla_configs(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch all SLA configurations, keyed by tenant_id + job_type."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/sla_configurations",
            headers=_get_headers(),
            params={"select": "*"},
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning(f"Failed to fetch SLA configs: {response.status_code}")
            return {}

        configs = response.json()
        result = {}
        for config in configs:
            key = f"{config['tenant_id']}_{config.get('job_type', 'default')}"
            result[key] = config

        return result
    except Exception as e:
        logger.error(f"Error fetching SLA configs: {str(e)}")
        return {}


async def _check_job_slas(
    client: httpx.AsyncClient,
    sla_configs: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    """Check all open job requisitions for SLA breaches."""
    result = {
        "checked": 0,
        "amber": 0,
        "red": 0,
        "alerts": [],
    }

    try:
        # Get all open jobs with SLA deadlines
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=_get_headers(),
            params={
                "status": "eq.open",
                "select": "id,tenant_id,title,job_sla_days,job_sla_deadline,job_opened_at",
            },
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning(f"Failed to fetch jobs: {response.status_code}")
            return result

        jobs = response.json()
        result["checked"] = len(jobs)

        for job in jobs:
            if not job.get("job_sla_deadline"):
                continue

            deadline = datetime.fromisoformat(job["job_sla_deadline"].replace("Z", "+00:00"))
            sla_days = job.get("job_sla_days", 30)

            # Get tenant SLA config for thresholds
            config_key = f"{job['tenant_id']}_default"
            config = sla_configs.get(config_key, {})
            amber_threshold = config.get("amber_threshold_percent", 75) / 100
            red_threshold = config.get("red_threshold_percent", 90) / 100

            # Calculate days elapsed and remaining
            opened_at = datetime.fromisoformat(job["job_opened_at"].replace("Z", "+00:00"))
            days_elapsed = (now - opened_at).days
            days_remaining = (deadline - now).days
            percent_elapsed = days_elapsed / sla_days if sla_days > 0 else 1

            alert_level = None
            if percent_elapsed >= red_threshold:
                alert_level = "red"
                result["red"] += 1
            elif percent_elapsed >= amber_threshold:
                alert_level = "amber"
                result["amber"] += 1

            if alert_level:
                # Check if alert already exists (avoid duplicates)
                existing = await _get_existing_alert(
                    client, "job_opening", str(job["id"]), alert_level
                )

                if not existing:
                    # Create alert record
                    alert_data = await _create_alert(
                        client,
                        job["tenant_id"],
                        alert_level,
                        "job_opening",
                        str(job["id"]),
                    )

                    # Get recruiter info for notification
                    recruiter_info = await _get_job_recruiter(client, str(job["id"]))

                    result["alerts"].append({
                        "alert_id": alert_data.get("id") if alert_data else None,
                        "level": alert_level,
                        "entity_type": "job_opening",
                        "job_id": str(job["id"]),
                        "job_title": job["title"],
                        "days_remaining": max(0, days_remaining),
                        "sla_days": sla_days,
                        "recruiter_email": recruiter_info.get("email"),
                        "recruiter_name": recruiter_info.get("name"),
                        "candidates_count": recruiter_info.get("candidates_count", 0),
                    })

    except Exception as e:
        logger.error(f"Error checking job SLAs: {str(e)}")

    return result


async def _check_assignment_slas(
    client: httpx.AsyncClient,
    sla_configs: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    """Check all active recruiter assignments for SLA breaches."""
    result = {
        "checked": 0,
        "amber": 0,
        "red": 0,
        "alerts": [],
    }

    try:
        # Get all active recruiter assignments with SLA deadlines
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/recruiter_assignments",
            headers=_get_headers(),
            params={
                "status": "eq.active",
                "select": "id,tenant_id,requisition_id,recruiter_id,sla_days,sla_deadline,assigned_at",
            },
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning(f"Failed to fetch assignments: {response.status_code}")
            return result

        assignments = response.json()
        result["checked"] = len(assignments)

        for assignment in assignments:
            if not assignment.get("sla_deadline"):
                continue

            deadline = datetime.fromisoformat(assignment["sla_deadline"].replace("Z", "+00:00"))
            sla_days = assignment.get("sla_days", 14)

            # Get tenant SLA config for thresholds
            config_key = f"{assignment['tenant_id']}_default"
            config = sla_configs.get(config_key, {})
            amber_threshold = config.get("amber_threshold_percent", 75) / 100
            red_threshold = config.get("red_threshold_percent", 90) / 100

            # Calculate elapsed and remaining
            assigned_at = datetime.fromisoformat(assignment["assigned_at"].replace("Z", "+00:00"))
            days_elapsed = (now - assigned_at).days
            days_remaining = (deadline - now).days
            percent_elapsed = days_elapsed / sla_days if sla_days > 0 else 1

            alert_level = None
            if percent_elapsed >= red_threshold:
                alert_level = "red"
                result["red"] += 1
            elif percent_elapsed >= amber_threshold:
                alert_level = "amber"
                result["amber"] += 1

            if alert_level:
                # Check if alert already exists
                existing = await _get_existing_alert(
                    client, "recruiter_assignment", str(assignment["id"]), alert_level
                )

                if not existing:
                    # Create alert record
                    alert_data = await _create_alert(
                        client,
                        assignment["tenant_id"],
                        alert_level,
                        "recruiter_assignment",
                        str(assignment["id"]),
                    )

                    # Get recruiter and job info
                    recruiter_info = await _get_recruiter_info(
                        client, assignment["recruiter_id"]
                    )
                    job_info = await _get_job_info(client, assignment["requisition_id"])

                    result["alerts"].append({
                        "alert_id": alert_data.get("id") if alert_data else None,
                        "level": alert_level,
                        "entity_type": "recruiter_assignment",
                        "job_id": str(assignment["requisition_id"]),
                        "job_title": job_info.get("title", "Unknown Position"),
                        "days_remaining": max(0, days_remaining),
                        "sla_days": sla_days,
                        "recruiter_email": recruiter_info.get("email"),
                        "recruiter_name": recruiter_info.get("name"),
                        "candidates_count": 0,  # Could be enhanced to count candidates
                    })

    except Exception as e:
        logger.error(f"Error checking assignment SLAs: {str(e)}")

    return result


async def _get_existing_alert(
    client: httpx.AsyncClient,
    entity_type: str,
    entity_id: str,
    alert_level: str,
) -> bool:
    """Check if an alert already exists for this entity and level (not acknowledged)."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/sla_alerts",
            headers=_get_headers(),
            params={
                "entity_type": f"eq.{entity_type}",
                "entity_id": f"eq.{entity_id}",
                "alert_type": f"eq.{alert_level}",
                "acknowledged_at": "is.null",
                "select": "id",
            },
            timeout=15,
        )

        return response.status_code == 200 and len(response.json()) > 0
    except Exception:
        return False


async def _create_alert(
    client: httpx.AsyncClient,
    tenant_id: str,
    alert_type: str,
    entity_type: str,
    entity_id: str,
) -> Dict[str, Any]:
    """Create a new SLA alert record."""
    try:
        from uuid import uuid4

        alert_data = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "alert_type": alert_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }

        response = await client.post(
            f"{settings.supabase_url}/rest/v1/sla_alerts",
            headers=_get_headers(),
            json=alert_data,
            timeout=15,
        )

        if response.status_code in (200, 201):
            return response.json()[0] if response.json() else alert_data

        logger.warning(f"Failed to create alert: {response.status_code}")
        return alert_data
    except Exception as e:
        logger.error(f"Error creating alert: {str(e)}")
        return {}


async def _get_job_recruiter(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    """Get the assigned recruiter for a job."""
    try:
        # Get latest active assignment
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/recruiter_assignments",
            headers=_get_headers(),
            params={
                "requisition_id": f"eq.{job_id}",
                "status": "eq.active",
                "select": "recruiter_id",
                "order": "assigned_at.desc",
                "limit": "1",
            },
            timeout=15,
        )

        if response.status_code == 200 and response.json():
            recruiter_id = response.json()[0]["recruiter_id"]
            return await _get_recruiter_info(client, recruiter_id)

        return {}
    except Exception:
        return {}


async def _get_recruiter_info(client: httpx.AsyncClient, recruiter_id: str) -> Dict[str, Any]:
    """Get recruiter details by ID."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/users",
            headers=_get_headers(),
            params={
                "id": f"eq.{recruiter_id}",
                "select": "id,email,full_name",
            },
            timeout=15,
        )

        if response.status_code == 200 and response.json():
            user = response.json()[0]
            return {
                "id": user["id"],
                "email": user.get("email"),
                "name": user.get("full_name"),
            }

        return {}
    except Exception:
        return {}


async def _get_job_info(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    """Get job requisition details by ID."""
    try:
        response = await client.get(
            f"{settings.supabase_url}/rest/v1/job_requisitions",
            headers=_get_headers(),
            params={
                "id": f"eq.{job_id}",
                "select": "id,title,department",
            },
            timeout=15,
        )

        if response.status_code == 200 and response.json():
            return response.json()[0]

        return {}
    except Exception:
        return {}


# Cron configuration for scheduled runs
# Run every hour at minute 0
check_sla_alerts_cron = cron(check_sla_alerts, hour=None, minute=0)
