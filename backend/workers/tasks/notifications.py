"""Notification Tasks - Background jobs for sending various notifications."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import httpx

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


async def send_interview_notification(
    ctx: Dict[str, Any],
    interview_id: str,
    tenant_id: str,
    notification_type: str = "scheduled",  # scheduled, reminder, cancelled
) -> Dict[str, Any]:
    """
    Background task to send interview-related notifications.

    Args:
        ctx: ARQ context
        interview_id: UUID of the interview
        tenant_id: UUID of the tenant
        notification_type: Type of notification to send

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending {notification_type} interview notification for interview={interview_id}")

    result = {
        "interview_id": interview_id,
        "notification_type": notification_type,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch interview details
            interview_response = await client.get(
                f"{settings.supabase_url}/rest/v1/interviews",
                headers=_get_headers(),
                params={
                    "id": f"eq.{interview_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "*",
                },
                timeout=30,
            )

            if interview_response.status_code != 200 or not interview_response.json():
                result["status"] = "failed"
                result["error"] = "Interview not found"
                return result

            interview = interview_response.json()[0]

            # Get application and candidate details
            application_response = await client.get(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={
                    "id": f"eq.{interview['application_id']}",
                    "select": "id,candidate_id,job_requisition_id",
                },
                timeout=30,
            )

            if application_response.status_code != 200 or not application_response.json():
                result["status"] = "failed"
                result["error"] = "Application not found"
                return result

            application = application_response.json()[0]

            # Get candidate details
            candidate_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['candidate_id']}",
                    "select": "id,first_name,last_name,email",
                },
                timeout=30,
            )

            if candidate_response.status_code != 200 or not candidate_response.json():
                result["status"] = "failed"
                result["error"] = "Candidate not found"
                return result

            candidate = candidate_response.json()[0]

            # Get job details
            job_response = await client.get(
                f"{settings.supabase_url}/rest/v1/job_requisitions",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['job_requisition_id']}",
                    "select": "id,title",
                },
                timeout=30,
            )

            job = job_response.json()[0] if job_response.json() else {}

            # Get interviewer names
            interviewer_ids = interview.get("interviewer_ids", [])
            interviewer_names = []
            if interviewer_ids:
                users_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/users",
                    headers=_get_headers(),
                    params={
                        "id": f"in.({','.join(interviewer_ids)})",
                        "select": "id,full_name",
                    },
                    timeout=30,
                )
                if users_response.status_code == 200:
                    interviewer_names = [u.get("full_name", "Interviewer") for u in users_response.json()]

            # Send notification based on type
            candidate_email = candidate.get("email")
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
            position_title = job.get("title", "Position")
            interview_datetime = datetime.fromisoformat(
                interview.get("scheduled_at", "").replace("Z", "+00:00")
            )
            interview_type = interview.get("interview_type", "video")
            location_or_link = interview.get("location") or interview.get("meeting_link", "TBD")

            if notification_type == "scheduled":
                email_result = await email_service.send_interview_scheduled(
                    candidate_email=candidate_email,
                    candidate_name=candidate_name,
                    interviewer_names=interviewer_names or ["Hiring Team"],
                    position_title=position_title,
                    interview_datetime=interview_datetime,
                    interview_type=interview_type,
                    location_or_link=location_or_link,
                )
            elif notification_type == "reminder":
                # Use same template with different subject
                email_result = await email_service.send_interview_scheduled(
                    candidate_email=candidate_email,
                    candidate_name=candidate_name,
                    interviewer_names=interviewer_names or ["Hiring Team"],
                    position_title=position_title,
                    interview_datetime=interview_datetime,
                    interview_type=interview_type,
                    location_or_link=location_or_link,
                    additional_info="This is a reminder about your upcoming interview.",
                )
            else:
                result["status"] = "skipped"
                result["error"] = f"Unknown notification type: {notification_type}"
                return result

            if email_result.get("success"):
                result["emails_sent"] = 1
                result["status"] = "completed"
            else:
                result["status"] = "failed"
                result["error"] = email_result.get("error")

        except Exception as e:
            logger.error(f"Interview notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def send_offer_notification(
    ctx: Dict[str, Any],
    offer_id: str,
    tenant_id: str,
    notification_type: str = "extended",  # extended, accepted, declined
) -> Dict[str, Any]:
    """
    Background task to send offer-related notifications.

    Args:
        ctx: ARQ context
        offer_id: UUID of the offer
        tenant_id: UUID of the tenant
        notification_type: Type of notification to send

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending {notification_type} offer notification for offer={offer_id}")

    result = {
        "offer_id": offer_id,
        "notification_type": notification_type,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch offer details
            offer_response = await client.get(
                f"{settings.supabase_url}/rest/v1/offers",
                headers=_get_headers(),
                params={
                    "id": f"eq.{offer_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "*",
                },
                timeout=30,
            )

            if offer_response.status_code != 200 or not offer_response.json():
                result["status"] = "failed"
                result["error"] = "Offer not found"
                return result

            offer = offer_response.json()[0]

            # Get candidate details
            candidate_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"eq.{offer['candidate_id']}",
                    "select": "id,first_name,last_name,email",
                },
                timeout=30,
            )

            if candidate_response.status_code != 200 or not candidate_response.json():
                result["status"] = "failed"
                result["error"] = "Candidate not found"
                return result

            candidate = candidate_response.json()[0]

            candidate_email = candidate.get("email")
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

            if notification_type == "extended":
                # Get hiring manager name
                hiring_manager_name = "Hiring Manager"
                if offer.get("hiring_manager_id"):
                    hm_response = await client.get(
                        f"{settings.supabase_url}/rest/v1/users",
                        headers=_get_headers(),
                        params={
                            "id": f"eq.{offer['hiring_manager_id']}",
                            "select": "full_name",
                        },
                        timeout=15,
                    )
                    if hm_response.status_code == 200 and hm_response.json():
                        hiring_manager_name = hm_response.json()[0].get("full_name", hiring_manager_name)

                start_date = datetime.fromisoformat(
                    offer.get("start_date", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")
                )

                expiration = None
                if offer.get("expiration_date"):
                    expiration = datetime.fromisoformat(offer["expiration_date"].replace("Z", "+00:00"))

                email_result = await email_service.send_offer_letter(
                    candidate_email=candidate_email,
                    candidate_name=candidate_name,
                    position_title=offer.get("position_title", "Position"),
                    department=offer.get("department", ""),
                    start_date=start_date,
                    salary=float(offer.get("base_salary", 0)),
                    hiring_manager_name=hiring_manager_name,
                    offer_expiration=expiration,
                )
            elif notification_type == "accepted":
                email_result = await email_service.send_application_status_update(
                    candidate_email=candidate_email,
                    candidate_name=candidate_name,
                    position_title=offer.get("position_title", "Position"),
                    new_status="offer_accepted",
                    custom_message="Congratulations! We're thrilled that you've accepted our offer. Welcome to the team!",
                )
            elif notification_type == "declined":
                email_result = await email_service.send_application_status_update(
                    candidate_email=candidate_email,
                    candidate_name=candidate_name,
                    position_title=offer.get("position_title", "Position"),
                    new_status="offer_declined",
                    custom_message="We understand you've decided to decline our offer. We wish you the best in your career journey.",
                )
            else:
                result["status"] = "skipped"
                result["error"] = f"Unknown notification type: {notification_type}"
                return result

            if email_result.get("success"):
                result["emails_sent"] = 1
                result["status"] = "completed"
            else:
                result["status"] = "failed"
                result["error"] = email_result.get("error")

        except Exception as e:
            logger.error(f"Offer notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def send_status_update_notification(
    ctx: Dict[str, Any],
    application_id: str,
    tenant_id: str,
    new_status: str,
    custom_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background task to send application status update notification.

    Args:
        ctx: ARQ context
        application_id: UUID of the application
        tenant_id: UUID of the tenant
        new_status: The new status to notify about
        custom_message: Optional custom message

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending status update notification for application={application_id}")

    result = {
        "application_id": application_id,
        "new_status": new_status,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch application details
            app_response = await client.get(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "id,candidate_id,job_requisition_id",
                },
                timeout=30,
            )

            if app_response.status_code != 200 or not app_response.json():
                result["status"] = "failed"
                result["error"] = "Application not found"
                return result

            application = app_response.json()[0]

            # Get candidate details
            candidate_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['candidate_id']}",
                    "select": "id,first_name,last_name,email",
                },
                timeout=30,
            )

            if candidate_response.status_code != 200 or not candidate_response.json():
                result["status"] = "failed"
                result["error"] = "Candidate not found"
                return result

            candidate = candidate_response.json()[0]

            # Get job details
            job_response = await client.get(
                f"{settings.supabase_url}/rest/v1/job_requisitions",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['job_requisition_id']}",
                    "select": "id,title",
                },
                timeout=30,
            )

            job = job_response.json()[0] if job_response.json() else {}

            candidate_email = candidate.get("email")
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
            position_title = job.get("title", "Position")

            email_result = await email_service.send_application_status_update(
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                position_title=position_title,
                new_status=new_status,
                custom_message=custom_message,
            )

            if email_result.get("success"):
                result["emails_sent"] = 1
                result["status"] = "completed"
            else:
                result["status"] = "failed"
                result["error"] = email_result.get("error")

        except Exception as e:
            logger.error(f"Status update notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def send_sla_alert_notification(
    ctx: Dict[str, Any],
    alert_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Background task to send SLA alert notification to recruiter.

    Args:
        ctx: ARQ context
        alert_id: UUID of the SLA alert
        tenant_id: UUID of the tenant

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending SLA alert notification for alert={alert_id}")

    result = {
        "alert_id": alert_id,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch alert details
            alert_response = await client.get(
                f"{settings.supabase_url}/rest/v1/sla_alerts",
                headers=_get_headers(),
                params={
                    "id": f"eq.{alert_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "*",
                },
                timeout=30,
            )

            if alert_response.status_code != 200 or not alert_response.json():
                result["status"] = "failed"
                result["error"] = "Alert not found"
                return result

            alert = alert_response.json()[0]

            # Get job details based on entity type
            job_id = alert.get("entity_id")
            if alert.get("entity_type") == "recruiter_assignment":
                # Get job ID from assignment
                assignment_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/recruiter_assignments",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{alert['entity_id']}",
                        "select": "requisition_id,recruiter_id,sla_days,sla_deadline",
                    },
                    timeout=30,
                )
                if assignment_response.status_code == 200 and assignment_response.json():
                    assignment = assignment_response.json()[0]
                    job_id = assignment.get("requisition_id")
                    recruiter_id = assignment.get("recruiter_id")

            # Get job details
            job_response = await client.get(
                f"{settings.supabase_url}/rest/v1/job_requisitions",
                headers=_get_headers(),
                params={
                    "id": f"eq.{job_id}",
                    "select": "id,title,job_sla_days,job_sla_deadline",
                },
                timeout=30,
            )

            job = job_response.json()[0] if job_response.json() else {}

            # Get recruiter details
            recruiter_id = locals().get("recruiter_id") or alert.get("recruiter_id")
            if not recruiter_id:
                # Try to get from job assignment
                assignment_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/recruiter_assignments",
                    headers=_get_headers(),
                    params={
                        "requisition_id": f"eq.{job_id}",
                        "status": "eq.active",
                        "select": "recruiter_id",
                        "limit": "1",
                    },
                    timeout=30,
                )
                if assignment_response.status_code == 200 and assignment_response.json():
                    recruiter_id = assignment_response.json()[0].get("recruiter_id")

            if not recruiter_id:
                result["status"] = "failed"
                result["error"] = "Could not determine recruiter"
                return result

            recruiter_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"eq.{recruiter_id}",
                    "select": "id,email,full_name",
                },
                timeout=30,
            )

            if recruiter_response.status_code != 200 or not recruiter_response.json():
                result["status"] = "failed"
                result["error"] = "Recruiter not found"
                return result

            recruiter = recruiter_response.json()[0]

            # Calculate days remaining
            deadline_str = job.get("job_sla_deadline")
            sla_days = job.get("job_sla_days", 30)
            days_remaining = 0

            if deadline_str:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
                days_remaining = max(0, (deadline - datetime.now(timezone.utc)).days)

            # Get candidate count in pipeline
            candidates_count = 0
            count_response = await client.get(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={
                    "job_requisition_id": f"eq.{job_id}",
                    "status": "eq.active",
                    "select": "id",
                },
                timeout=30,
            )
            if count_response.status_code == 200:
                candidates_count = len(count_response.json())

            email_result = await email_service.send_sla_alert(
                recruiter_email=recruiter.get("email"),
                recruiter_name=recruiter.get("full_name", "Recruiter"),
                alert_level=alert.get("alert_type", "amber"),
                job_title=job.get("title", "Unknown Position"),
                job_id=str(job_id),
                days_remaining=days_remaining,
                sla_days=sla_days,
                candidates_in_pipeline=candidates_count,
            )

            if email_result.get("success"):
                result["emails_sent"] = 1
                result["status"] = "completed"
            else:
                result["status"] = "failed"
                result["error"] = email_result.get("error")

        except Exception as e:
            logger.error(f"SLA alert notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def send_scorecard_reminder_notification(
    ctx: Dict[str, Any],
    interview_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Background task to send scorecard reminder to interviewer.

    Args:
        ctx: ARQ context
        interview_id: UUID of the interview
        tenant_id: UUID of the tenant

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending scorecard reminder for interview={interview_id}")

    result = {
        "interview_id": interview_id,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch interview details
            interview_response = await client.get(
                f"{settings.supabase_url}/rest/v1/interviews",
                headers=_get_headers(),
                params={
                    "id": f"eq.{interview_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "id,application_id,interviewer_ids,scheduled_at",
                },
                timeout=30,
            )

            if interview_response.status_code != 200 or not interview_response.json():
                result["status"] = "failed"
                result["error"] = "Interview not found"
                return result

            interview = interview_response.json()[0]

            # Get application and candidate details
            app_response = await client.get(
                f"{settings.supabase_url}/rest/v1/applications",
                headers=_get_headers(),
                params={
                    "id": f"eq.{interview['application_id']}",
                    "select": "id,candidate_id,job_requisition_id",
                },
                timeout=30,
            )

            application = app_response.json()[0] if app_response.json() else {}

            # Get candidate name
            candidate_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['candidate_id']}",
                    "select": "first_name,last_name",
                },
                timeout=30,
            )
            candidate = candidate_response.json()[0] if candidate_response.json() else {}
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

            # Get job title
            job_response = await client.get(
                f"{settings.supabase_url}/rest/v1/job_requisitions",
                headers=_get_headers(),
                params={
                    "id": f"eq.{application['job_requisition_id']}",
                    "select": "title",
                },
                timeout=30,
            )
            job = job_response.json()[0] if job_response.json() else {}
            position_title = job.get("title", "Position")

            interview_date = datetime.fromisoformat(
                interview.get("scheduled_at", "").replace("Z", "+00:00")
            )

            # Check which interviewers haven't submitted scorecards
            interviewer_ids = interview.get("interviewer_ids", [])

            for interviewer_id in interviewer_ids:
                # Check if scorecard exists
                feedback_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/interview_feedback",
                    headers=_get_headers(),
                    params={
                        "application_id": f"eq.{interview['application_id']}",
                        "interviewer_id": f"eq.{interviewer_id}",
                        "select": "id",
                    },
                    timeout=15,
                )

                if feedback_response.status_code == 200 and feedback_response.json():
                    continue  # Scorecard already submitted

                # Get interviewer details
                user_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/users",
                    headers=_get_headers(),
                    params={
                        "id": f"eq.{interviewer_id}",
                        "select": "email,full_name",
                    },
                    timeout=15,
                )

                if user_response.status_code == 200 and user_response.json():
                    interviewer = user_response.json()[0]

                    email_result = await email_service.send_scorecard_reminder(
                        interviewer_email=interviewer.get("email"),
                        interviewer_name=interviewer.get("full_name", "Interviewer"),
                        candidate_name=candidate_name,
                        position_title=position_title,
                        interview_date=interview_date,
                    )

                    if email_result.get("success"):
                        result["emails_sent"] += 1

            result["status"] = "completed"

        except Exception as e:
            logger.error(f"Scorecard reminder notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result


async def send_mention_notification(
    ctx: Dict[str, Any],
    comment_id: str,
    mentioned_user_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Background task to send @mention notification.

    Args:
        ctx: ARQ context
        comment_id: UUID of the comment
        mentioned_user_id: UUID of the mentioned user
        tenant_id: UUID of the tenant

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending mention notification for comment={comment_id}")

    result = {
        "comment_id": comment_id,
        "mentioned_user_id": mentioned_user_id,
        "status": "pending",
        "emails_sent": 0,
        "error": None,
    }

    email_service = get_email_service()

    async with httpx.AsyncClient() as client:
        try:
            # Fetch comment details
            comment_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidate_comments",
                headers=_get_headers(),
                params={
                    "id": f"eq.{comment_id}",
                    "tenant_id": f"eq.{tenant_id}",
                    "select": "id,candidate_id,author_id,content",
                },
                timeout=30,
            )

            if comment_response.status_code != 200 or not comment_response.json():
                result["status"] = "failed"
                result["error"] = "Comment not found"
                return result

            comment = comment_response.json()[0]

            # Get author details
            author_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"eq.{comment['author_id']}",
                    "select": "full_name",
                },
                timeout=15,
            )
            author = author_response.json()[0] if author_response.json() else {}
            mentioner_name = author.get("full_name", "Someone")

            # Get mentioned user details
            user_response = await client.get(
                f"{settings.supabase_url}/rest/v1/users",
                headers=_get_headers(),
                params={
                    "id": f"eq.{mentioned_user_id}",
                    "select": "email,full_name",
                },
                timeout=15,
            )

            if user_response.status_code != 200 or not user_response.json():
                result["status"] = "failed"
                result["error"] = "Mentioned user not found"
                return result

            mentioned_user = user_response.json()[0]

            # Get candidate name
            candidate_response = await client.get(
                f"{settings.supabase_url}/rest/v1/candidates",
                headers=_get_headers(),
                params={
                    "id": f"eq.{comment['candidate_id']}",
                    "select": "first_name,last_name",
                },
                timeout=15,
            )
            candidate = candidate_response.json()[0] if candidate_response.json() else {}
            candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

            # Truncate comment for preview
            comment_preview = comment.get("content", "")[:200]
            if len(comment.get("content", "")) > 200:
                comment_preview += "..."

            email_result = await email_service.send_mention_notification(
                mentioned_user_email=mentioned_user.get("email"),
                mentioned_user_name=mentioned_user.get("full_name", "User"),
                mentioner_name=mentioner_name,
                candidate_name=candidate_name or "a candidate",
                comment_preview=comment_preview,
            )

            if email_result.get("success"):
                result["emails_sent"] = 1
                result["status"] = "completed"
            else:
                result["status"] = "failed"
                result["error"] = email_result.get("error")

        except Exception as e:
            logger.error(f"Mention notification failed: {str(e)}")
            result["status"] = "failed"
            result["error"] = str(e)

    return result
