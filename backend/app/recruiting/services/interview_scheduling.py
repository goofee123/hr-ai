"""Interview scheduling service for managing interview requests, availability, and scheduling."""

import logging
import secrets
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from app.core.supabase_client import get_supabase_client
from app.recruiting.services.calendar_service import (
    get_calendar_service,
    CalendarProvider,
    CalendarEventResult,
)
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)


class InterviewSchedulingService:
    """
    Service for managing interview scheduling workflow.

    Handles:
    - Creating interview requests
    - Collecting interviewer availability
    - Scheduling interviews
    - Candidate self-scheduling
    - Calendar integration
    - Email notifications
    - Reminders
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.calendar_service = get_calendar_service()
        self.email_service = get_email_service()

    # =========================================================================
    # Interview Request Management
    # =========================================================================

    async def create_interview_request(
        self,
        tenant_id: UUID,
        application_id: UUID,
        stage_name: str,
        interview_type: str,
        title: str,
        interviewer_ids: List[UUID],
        created_by: UUID,
        duration_minutes: int = 60,
        description: Optional[str] = None,
        preferred_date_range_start: Optional[date] = None,
        preferred_date_range_end: Optional[date] = None,
        location: Optional[str] = None,
        video_link: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an interview scheduling request.

        This creates the interview request and optionally sends availability
        requests to interviewers.
        """
        # Generate unique request ID
        request_data = {
            "tenant_id": str(tenant_id),
            "application_id": str(application_id),
            "stage_name": stage_name,
            "interview_type": interview_type,
            "title": title,
            "description": description,
            "duration_minutes": duration_minutes,
            "interviewer_ids": [str(uid) for uid in interviewer_ids],
            "preferred_date_range_start": preferred_date_range_start.isoformat() if preferred_date_range_start else None,
            "preferred_date_range_end": preferred_date_range_end.isoformat() if preferred_date_range_end else None,
            "location": location,
            "video_link": video_link,
            "notes": notes,
            "status": "pending_slots",
            "created_by": str(created_by),
        }

        result = await self.supabase.insert("interview_requests", request_data)

        logger.info(
            f"Created interview request {result.get('id')} for application {application_id}"
        )

        return result

    async def get_interview_request(
        self,
        tenant_id: UUID,
        request_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get an interview request with related data."""
        request = await self.supabase.select(
            "interview_requests",
            "*",
            filters={
                "id": str(request_id),
                "tenant_id": str(tenant_id),
            },
            single=True,
        )

        if not request:
            return None

        # Get application and candidate info
        application = await self.supabase.select(
            "applications",
            "id, candidate_id, requisition_id",
            filters={"id": request["application_id"]},
            single=True,
        )

        if application:
            candidate = await self.supabase.select(
                "candidates",
                "id, first_name, last_name, email",
                filters={"id": application["candidate_id"]},
                single=True,
            )
            if candidate:
                request["candidate_name"] = f"{candidate['first_name']} {candidate['last_name']}"
                request["candidate_email"] = candidate["email"]

            # Get job title
            requisition = await self.supabase.select(
                "job_requisitions",
                "title",
                filters={"id": application["requisition_id"]},
                single=True,
            )
            if requisition:
                request["position_title"] = requisition["title"]

        # Get availability requests
        availability_requests = await self.supabase.select(
            "interviewer_availability",
            "*",
            filters={"interview_request_id": str(request_id)},
            return_empty_on_404=True,
        ) or []

        request["availability_requests"] = availability_requests

        return request

    async def list_interview_requests(
        self,
        tenant_id: UUID,
        application_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List interview requests with pagination."""
        filters = {"tenant_id": str(tenant_id)}

        if application_id:
            filters["application_id"] = str(application_id)
        if status:
            filters["status"] = status

        # Get total count (simplified)
        all_requests = await self.supabase.select(
            "interview_requests",
            "id",
            filters=filters,
            return_empty_on_404=True,
        ) or []
        total = len(all_requests)

        # Get paginated results
        requests = await self.supabase.select(
            "interview_requests",
            "*",
            filters=filters,
            return_empty_on_404=True,
        ) or []

        # Sort by created_at desc and paginate
        requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        start = (page - 1) * page_size
        end = start + page_size
        requests = requests[start:end]

        return requests, total

    # =========================================================================
    # Interviewer Availability
    # =========================================================================

    async def request_interviewer_availability(
        self,
        tenant_id: UUID,
        interview_request_id: UUID,
        interviewer_id: UUID,
        date_range_start: date,
        date_range_end: date,
        duration_minutes: int = 60,
        timezone: str = "America/New_York",
        expires_in_hours: int = 48,
        notes: Optional[str] = None,
        send_email: bool = True,
    ) -> Dict[str, Any]:
        """
        Request availability from an interviewer.

        Creates an availability request record and optionally sends an email.
        """
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        availability_data = {
            "tenant_id": str(tenant_id),
            "interview_request_id": str(interview_request_id),
            "interviewer_id": str(interviewer_id),
            "date_range_start": date_range_start.isoformat(),
            "date_range_end": date_range_end.isoformat(),
            "duration_minutes": duration_minutes,
            "timezone": timezone,
            "status": "pending",
            "expires_at": expires_at.isoformat(),
            "notes": notes,
            "available_slots": [],
        }

        result = await self.supabase.insert("interviewer_availability", availability_data)

        # Send email notification if requested
        if send_email:
            # Get interviewer info
            interviewer = await self.supabase.select(
                "users",
                "email, first_name, last_name",
                filters={"id": str(interviewer_id)},
                single=True,
            )

            if interviewer:
                # TODO: Send availability request email
                logger.info(
                    f"Would send availability request email to {interviewer['email']}"
                )

        logger.info(
            f"Created availability request {result.get('id')} for interviewer {interviewer_id}"
        )

        return result

    async def submit_interviewer_availability(
        self,
        tenant_id: UUID,
        availability_id: UUID,
        interviewer_id: UUID,
        available_slots: List[Dict[str, Any]],
        weekly_patterns: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit availability for an interviewer.

        Updates the availability request with the submitted slots.
        """
        import json

        # Verify the availability request belongs to this interviewer
        existing = await self.supabase.select(
            "interviewer_availability",
            "*",
            filters={
                "id": str(availability_id),
                "tenant_id": str(tenant_id),
                "interviewer_id": str(interviewer_id),
            },
            single=True,
        )

        if not existing:
            raise ValueError("Availability request not found")

        if existing["status"] == "submitted":
            raise ValueError("Availability already submitted")

        # Serialize slots for storage
        slots_json = json.dumps([
            {
                "start_time": slot["start_time"].isoformat() if isinstance(slot["start_time"], datetime) else slot["start_time"],
                "end_time": slot["end_time"].isoformat() if isinstance(slot["end_time"], datetime) else slot["end_time"],
                "timezone": slot.get("timezone", "America/New_York"),
            }
            for slot in available_slots
        ])

        update_data = {
            "available_slots": slots_json,
            "status": "submitted",
            "submitted_at": datetime.utcnow().isoformat(),
            "notes": notes,
        }

        if weekly_patterns:
            update_data["weekly_patterns"] = json.dumps(weekly_patterns)

        result = await self.supabase.update(
            "interviewer_availability",
            update_data,
            filters={"id": str(availability_id)},
        )

        # Check if all interviewers have submitted - update interview request status
        await self._check_availability_complete(tenant_id, existing["interview_request_id"])

        logger.info(
            f"Interviewer {interviewer_id} submitted availability with {len(available_slots)} slots"
        )

        return result

    async def _check_availability_complete(
        self, tenant_id: UUID, interview_request_id: str
    ) -> bool:
        """Check if all interviewers have submitted availability."""
        # Get all availability requests for this interview
        availabilities = await self.supabase.select(
            "interviewer_availability",
            "*",
            filters={
                "tenant_id": str(tenant_id),
                "interview_request_id": interview_request_id,
            },
            return_empty_on_404=True,
        ) or []

        all_submitted = all(a["status"] == "submitted" for a in availabilities)

        if all_submitted and availabilities:
            # Update interview request status
            await self.supabase.update(
                "interview_requests",
                {"status": "pending_candidate"},
                filters={"id": interview_request_id},
            )
            return True

        return False

    # =========================================================================
    # Interview Scheduling
    # =========================================================================

    async def schedule_interview(
        self,
        tenant_id: UUID,
        interview_request_id: UUID,
        scheduled_at: datetime,
        organizer_id: UUID,
        timezone: str = "America/New_York",
        location: Optional[str] = None,
        video_link: Optional[str] = None,
        send_calendar_invites: bool = True,
        send_candidate_email: bool = True,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule an interview at a specific time.

        Creates the interview schedule, optionally creates calendar events,
        and sends notifications.
        """
        # Get the interview request
        request = await self.get_interview_request(tenant_id, UUID(interview_request_id))
        if not request:
            raise ValueError("Interview request not found")

        # Calculate end time
        end_time = scheduled_at + timedelta(minutes=request["duration_minutes"])

        # Create interview schedule record
        schedule_data = {
            "tenant_id": str(tenant_id),
            "application_id": request["application_id"],
            "interview_request_id": interview_request_id,
            "interview_type": request["interview_type"],
            "title": request["title"],
            "description": request.get("description"),
            "scheduled_at": scheduled_at.isoformat(),
            "duration_minutes": request["duration_minutes"],
            "timezone": timezone,
            "location": location or request.get("location"),
            "video_link": video_link or request.get("video_link"),
            "interviewer_ids": request["interviewer_ids"],
            "organizer_id": str(organizer_id),
            "status": "scheduled",
            "feedback_due_by": (scheduled_at + timedelta(days=1)).isoformat(),
        }

        schedule = await self.supabase.insert("interview_schedules", schedule_data)

        # Update interview request status
        await self.supabase.update(
            "interview_requests",
            {"status": "scheduled"},
            filters={"id": interview_request_id},
        )

        # Create calendar event if requested
        if send_calendar_invites:
            # Get interviewer emails
            interviewer_emails = []
            for interviewer_id in request["interviewer_ids"]:
                user = await self.supabase.select(
                    "users",
                    "email",
                    filters={"id": interviewer_id},
                    single=True,
                )
                if user:
                    interviewer_emails.append(user["email"])

            # Add candidate email
            all_attendees = interviewer_emails.copy()
            if request.get("candidate_email"):
                all_attendees.append(request["candidate_email"])

            # Create calendar event
            calendar_result = await self.calendar_service.create_interview_event(
                title=request["title"],
                description=f"Interview with {request.get('candidate_name', 'Candidate')}\n\n{request.get('description', '')}",
                start_time=scheduled_at,
                end_time=end_time,
                timezone=timezone,
                attendee_emails=all_attendees,
                location=schedule_data["location"],
                video_link=schedule_data["video_link"],
            )

            if calendar_result.success and calendar_result.event_id:
                await self.supabase.update(
                    "interview_schedules",
                    {"calendar_event_id": calendar_result.event_id},
                    filters={"id": schedule["id"]},
                )

        # Send candidate email if requested
        if send_candidate_email and request.get("candidate_email"):
            # Get interviewer names
            interviewer_names = []
            for interviewer_id in request["interviewer_ids"]:
                user = await self.supabase.select(
                    "users",
                    "first_name, last_name",
                    filters={"id": interviewer_id},
                    single=True,
                )
                if user:
                    interviewer_names.append(f"{user['first_name']} {user['last_name']}")

            await self.email_service.send_interview_scheduled(
                candidate_email=request["candidate_email"],
                candidate_name=request.get("candidate_name", "Candidate"),
                interviewer_names=interviewer_names,
                position_title=request.get("position_title", "Position"),
                interview_datetime=scheduled_at,
                interview_type=request["interview_type"],
                location_or_link=schedule_data["video_link"] or schedule_data["location"] or "TBD",
                additional_info=custom_message,
            )

        logger.info(
            f"Scheduled interview {schedule['id']} for {scheduled_at}"
        )

        return schedule

    async def reschedule_interview(
        self,
        tenant_id: UUID,
        schedule_id: UUID,
        new_scheduled_at: datetime,
        reason: Optional[str] = None,
        notify_participants: bool = True,
    ) -> Dict[str, Any]:
        """Reschedule an existing interview."""
        # Get existing schedule
        schedule = await self.supabase.select(
            "interview_schedules",
            "*",
            filters={
                "id": str(schedule_id),
                "tenant_id": str(tenant_id),
            },
            single=True,
        )

        if not schedule:
            raise ValueError("Interview schedule not found")

        old_time = schedule["scheduled_at"]
        end_time = new_scheduled_at + timedelta(minutes=schedule["duration_minutes"])

        # Update schedule
        update_data = {
            "scheduled_at": new_scheduled_at.isoformat(),
            "status": "rescheduled",
        }

        result = await self.supabase.update(
            "interview_schedules",
            update_data,
            filters={"id": str(schedule_id)},
        )

        # Update calendar event if exists
        if schedule.get("calendar_event_id"):
            await self.calendar_service.update_interview_event(
                event_id=schedule["calendar_event_id"],
                title=schedule["title"],
                description=schedule.get("description", ""),
                start_time=new_scheduled_at,
                end_time=end_time,
                timezone=schedule.get("timezone", "America/New_York"),
                attendee_emails=[],  # Calendar API will maintain existing attendees
            )

        logger.info(
            f"Rescheduled interview {schedule_id} from {old_time} to {new_scheduled_at}"
        )

        return result

    async def cancel_interview(
        self,
        tenant_id: UUID,
        schedule_id: UUID,
        reason: str,
        notify_participants: bool = True,
    ) -> Dict[str, Any]:
        """Cancel a scheduled interview."""
        # Get existing schedule
        schedule = await self.supabase.select(
            "interview_schedules",
            "*",
            filters={
                "id": str(schedule_id),
                "tenant_id": str(tenant_id),
            },
            single=True,
        )

        if not schedule:
            raise ValueError("Interview schedule not found")

        # Update status
        result = await self.supabase.update(
            "interview_schedules",
            {
                "status": "cancelled",
                "notes": f"Cancelled: {reason}",
            },
            filters={"id": str(schedule_id)},
        )

        # Cancel calendar event if exists
        if schedule.get("calendar_event_id"):
            await self.calendar_service.cancel_interview_event(
                event_id=schedule["calendar_event_id"],
            )

        logger.info(f"Cancelled interview {schedule_id}: {reason}")

        return result

    # =========================================================================
    # Self-Scheduling Links
    # =========================================================================

    async def create_self_scheduling_link(
        self,
        tenant_id: UUID,
        interview_request_id: UUID,
        available_slots: List[Dict[str, Any]],
        created_by: UUID,
        expires_in_hours: int = 72,
        max_reschedules: int = 2,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a self-scheduling link for a candidate.

        The candidate can use this link to pick a time slot without
        needing to log in.
        """
        import json

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        # Serialize slots
        slots_json = json.dumps([
            {
                "start_time": slot["start_time"].isoformat() if isinstance(slot["start_time"], datetime) else slot["start_time"],
                "end_time": slot["end_time"].isoformat() if isinstance(slot["end_time"], datetime) else slot["end_time"],
                "timezone": slot.get("timezone", "America/New_York"),
            }
            for slot in available_slots
        ])

        link_data = {
            "tenant_id": str(tenant_id),
            "interview_request_id": str(interview_request_id),
            "token": token,
            "available_slots": slots_json,
            "expires_at": expires_at.isoformat(),
            "max_reschedules": max_reschedules,
            "reschedule_count": 0,
            "is_used": False,
            "custom_message": custom_message,
            "created_by": str(created_by),
        }

        result = await self.supabase.insert("self_scheduling_links", link_data)

        # Build link URL
        from app.config import get_settings
        settings = get_settings()
        base_url = getattr(settings, 'frontend_url', 'http://localhost:3002')
        result["link_url"] = f"{base_url}/schedule/{token}"

        logger.info(
            f"Created self-scheduling link for interview request {interview_request_id}"
        )

        return result

    async def get_self_scheduling_link(
        self,
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get self-scheduling link details by token.

        This is a public endpoint that doesn't require authentication.
        """
        import json

        link = await self.supabase.select(
            "self_scheduling_links",
            "*",
            filters={"token": token},
            single=True,
        )

        if not link:
            return None

        # Check if expired
        if link.get("expires_at"):
            expires_at = datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00"))
            if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
                return {"error": "Link has expired", "is_expired": True}

        # Check if already used and no reschedules left
        if link["is_used"] and link["reschedule_count"] >= link["max_reschedules"]:
            return {"error": "Link has been used", "is_used": True}

        # Parse slots
        if isinstance(link.get("available_slots"), str):
            link["available_slots"] = json.loads(link["available_slots"])

        # Get interview request details
        request = await self.supabase.select(
            "interview_requests",
            "*",
            filters={"id": link["interview_request_id"]},
            single=True,
        )

        if request:
            link["interview_type"] = request.get("interview_type")
            link["duration_minutes"] = request.get("duration_minutes")
            link["title"] = request.get("title")

            # Get candidate name
            application = await self.supabase.select(
                "applications",
                "candidate_id, requisition_id",
                filters={"id": request["application_id"]},
                single=True,
            )

            if application:
                candidate = await self.supabase.select(
                    "candidates",
                    "first_name, last_name",
                    filters={"id": application["candidate_id"]},
                    single=True,
                )
                if candidate:
                    link["candidate_name"] = f"{candidate['first_name']} {candidate['last_name']}"

                requisition = await self.supabase.select(
                    "job_requisitions",
                    "title",
                    filters={"id": application["requisition_id"]},
                    single=True,
                )
                if requisition:
                    link["position_title"] = requisition["title"]

        return link

    async def select_slot_from_link(
        self,
        token: str,
        slot_index: int,
        candidate_timezone: str = "America/New_York",
        candidate_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Candidate selects a time slot from self-scheduling link.

        This schedules the interview and marks the link as used.
        """
        import json

        # Get link details
        link = await self.get_self_scheduling_link(token)

        if not link:
            raise ValueError("Invalid or expired scheduling link")

        if link.get("error"):
            raise ValueError(link["error"])

        # Validate slot index
        slots = link["available_slots"]
        if slot_index < 0 or slot_index >= len(slots):
            raise ValueError("Invalid slot index")

        selected_slot = slots[slot_index]

        # Parse datetime
        start_time = datetime.fromisoformat(selected_slot["start_time"].replace("Z", "+00:00"))
        if start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)

        # Get interview request for scheduling
        request = await self.supabase.select(
            "interview_requests",
            "*",
            filters={"id": link["interview_request_id"]},
            single=True,
        )

        if not request:
            raise ValueError("Interview request not found")

        # Schedule the interview
        schedule = await self.schedule_interview(
            tenant_id=UUID(link["tenant_id"]),
            interview_request_id=link["interview_request_id"],
            scheduled_at=start_time,
            organizer_id=UUID(request["created_by"]),
            timezone=candidate_timezone,
            send_calendar_invites=True,
            send_candidate_email=True,
            custom_message=candidate_notes,
        )

        # Mark link as used
        await self.supabase.update(
            "self_scheduling_links",
            {
                "is_used": True,
                "selected_slot": json.dumps(selected_slot),
            },
            filters={"token": token},
        )

        logger.info(f"Candidate selected slot {slot_index} from link {token}")

        return schedule

    # =========================================================================
    # Reminders
    # =========================================================================

    async def schedule_reminders(
        self,
        tenant_id: UUID,
        schedule_id: UUID,
        reminder_hours: List[int] = [24, 1],
    ) -> List[Dict[str, Any]]:
        """Schedule interview reminders."""
        # Get schedule details
        schedule = await self.supabase.select(
            "interview_schedules",
            "*",
            filters={
                "id": str(schedule_id),
                "tenant_id": str(tenant_id),
            },
            single=True,
        )

        if not schedule:
            raise ValueError("Interview schedule not found")

        scheduled_at = datetime.fromisoformat(schedule["scheduled_at"].replace("Z", "+00:00"))
        reminders = []

        for hours_before in reminder_hours:
            reminder_time = scheduled_at - timedelta(hours=hours_before)

            if reminder_time > datetime.utcnow().replace(tzinfo=scheduled_at.tzinfo):
                reminder_data = {
                    "tenant_id": str(tenant_id),
                    "interview_schedule_id": str(schedule_id),
                    "scheduled_for": reminder_time.isoformat(),
                    "hours_before": hours_before,
                    "status": "pending",
                }

                result = await self.supabase.insert("interview_reminders", reminder_data)
                reminders.append(result)

        return reminders

    async def get_pending_reminders(
        self,
        tenant_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Get reminders that are due to be sent."""
        now = datetime.utcnow().isoformat()

        filters = {
            "status": "pending",
        }
        if tenant_id:
            filters["tenant_id"] = str(tenant_id)

        reminders = await self.supabase.select(
            "interview_reminders",
            "*",
            filters=filters,
            return_empty_on_404=True,
        ) or []

        # Filter to only reminders that are due
        due_reminders = [
            r for r in reminders
            if r.get("scheduled_for", "") <= now
        ]

        return due_reminders

    # =========================================================================
    # Interview Metrics
    # =========================================================================

    async def get_interview_metrics(
        self,
        tenant_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get interview scheduling metrics."""
        filters = {"tenant_id": str(tenant_id)}

        schedules = await self.supabase.select(
            "interview_schedules",
            "*",
            filters=filters,
            return_empty_on_404=True,
        ) or []

        # Filter by date range if provided
        if start_date:
            schedules = [
                s for s in schedules
                if s.get("created_at", "")[:10] >= start_date.isoformat()
            ]
        if end_date:
            schedules = [
                s for s in schedules
                if s.get("created_at", "")[:10] <= end_date.isoformat()
            ]

        # Calculate metrics
        total_scheduled = len(schedules)
        completed = len([s for s in schedules if s.get("status") == "completed"])
        cancelled = len([s for s in schedules if s.get("status") == "cancelled"])
        no_shows = len([s for s in schedules if s.get("status") == "no_show"])

        # Group by type
        by_type: Dict[str, int] = {}
        by_stage: Dict[str, int] = {}

        for s in schedules:
            interview_type = s.get("interview_type", "unknown")
            by_type[interview_type] = by_type.get(interview_type, 0) + 1

            # Would need to join with applications to get stage
            # For now, use interview_type as proxy

        return {
            "total_scheduled": total_scheduled,
            "total_completed": completed,
            "total_cancelled": cancelled,
            "total_no_shows": no_shows,
            "completion_rate": (completed / total_scheduled * 100) if total_scheduled > 0 else 0,
            "cancellation_rate": (cancelled / total_scheduled * 100) if total_scheduled > 0 else 0,
            "interviews_by_type": by_type,
            "interviews_by_stage": by_stage,
        }


# Singleton instance
_scheduling_service: Optional[InterviewSchedulingService] = None


def get_interview_scheduling_service() -> InterviewSchedulingService:
    """Get or create the interview scheduling service singleton."""
    global _scheduling_service
    if _scheduling_service is None:
        _scheduling_service = InterviewSchedulingService()
    return _scheduling_service
