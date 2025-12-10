"""Calendar integration service for Google Calendar and Outlook."""

import logging
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CalendarProvider(str, Enum):
    """Supported calendar providers."""
    GOOGLE = "google"
    OUTLOOK = "outlook"
    NONE = "none"


class CalendarEvent(BaseModel):
    """Calendar event structure."""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: str = "America/New_York"
    location: Optional[str] = None
    video_link: Optional[str] = None
    attendees: List[str] = []  # Email addresses
    organizer_email: Optional[str] = None
    reminders: List[int] = [60, 15]  # Minutes before


class CalendarEventResult(BaseModel):
    """Result of calendar operation."""
    success: bool
    event_id: Optional[str] = None
    event_link: Optional[str] = None
    error: Optional[str] = None
    provider: CalendarProvider


class CalendarToken(BaseModel):
    """OAuth tokens for calendar access."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    provider: CalendarProvider


# =============================================================================
# Abstract Calendar Provider
# =============================================================================

class CalendarProviderBase(ABC):
    """Abstract base class for calendar providers."""

    @abstractmethod
    async def create_event(self, event: CalendarEvent, user_token: CalendarToken) -> CalendarEventResult:
        """Create a calendar event."""
        pass

    @abstractmethod
    async def update_event(
        self, event_id: str, event: CalendarEvent, user_token: CalendarToken
    ) -> CalendarEventResult:
        """Update an existing calendar event."""
        pass

    @abstractmethod
    async def delete_event(self, event_id: str, user_token: CalendarToken) -> CalendarEventResult:
        """Delete a calendar event."""
        pass

    @abstractmethod
    async def get_free_busy(
        self,
        email: str,
        start_time: datetime,
        end_time: datetime,
        user_token: CalendarToken,
    ) -> List[Dict[str, datetime]]:
        """Get free/busy information for a user."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> CalendarToken:
        """Refresh an expired access token."""
        pass


# =============================================================================
# Google Calendar Provider
# =============================================================================

class GoogleCalendarProvider(CalendarProviderBase):
    """Google Calendar API integration."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base = "https://www.googleapis.com/calendar/v3"

    async def create_event(self, event: CalendarEvent, user_token: CalendarToken) -> CalendarEventResult:
        """Create a Google Calendar event."""
        try:
            # Build event body
            event_body = {
                "summary": event.title,
                "description": event.description or "",
                "start": {
                    "dateTime": event.start_time.isoformat(),
                    "timeZone": event.timezone,
                },
                "end": {
                    "dateTime": event.end_time.isoformat(),
                    "timeZone": event.timezone,
                },
                "attendees": [{"email": email} for email in event.attendees],
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": m} for m in event.reminders
                    ] + [
                        {"method": "popup", "minutes": m} for m in event.reminders
                    ],
                },
            }

            if event.location:
                event_body["location"] = event.location

            if event.video_link:
                event_body["description"] = f"{event.description or ''}\n\nVideo Link: {event.video_link}"
                # Request conferenceData for Google Meet
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": secrets.token_hex(16),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"}
                    }
                }

            # In production, this would make actual API call
            # For now, simulate success
            logger.info(f"[SIMULATED] Creating Google Calendar event: {event.title}")

            return CalendarEventResult(
                success=True,
                event_id=f"gcal_{secrets.token_hex(12)}",
                event_link=f"https://calendar.google.com/calendar/event?eid={secrets.token_hex(8)}",
                provider=CalendarProvider.GOOGLE,
            )

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.GOOGLE,
            )

    async def update_event(
        self, event_id: str, event: CalendarEvent, user_token: CalendarToken
    ) -> CalendarEventResult:
        """Update a Google Calendar event."""
        try:
            logger.info(f"[SIMULATED] Updating Google Calendar event: {event_id}")

            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=CalendarProvider.GOOGLE,
            )

        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.GOOGLE,
            )

    async def delete_event(self, event_id: str, user_token: CalendarToken) -> CalendarEventResult:
        """Delete a Google Calendar event."""
        try:
            logger.info(f"[SIMULATED] Deleting Google Calendar event: {event_id}")

            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=CalendarProvider.GOOGLE,
            )

        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.GOOGLE,
            )

    async def get_free_busy(
        self,
        email: str,
        start_time: datetime,
        end_time: datetime,
        user_token: CalendarToken,
    ) -> List[Dict[str, datetime]]:
        """Get free/busy information from Google Calendar."""
        try:
            logger.info(f"[SIMULATED] Getting free/busy for {email}")

            # Return empty list (all free) in simulation
            return []

        except Exception as e:
            logger.error(f"Failed to get free/busy from Google Calendar: {e}")
            return []

    async def refresh_token(self, refresh_token: str) -> CalendarToken:
        """Refresh Google OAuth token."""
        # In production, this would call Google OAuth endpoint
        return CalendarToken(
            access_token=f"new_access_{secrets.token_hex(16)}",
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            provider=CalendarProvider.GOOGLE,
        )


# =============================================================================
# Outlook Calendar Provider
# =============================================================================

class OutlookCalendarProvider(CalendarProviderBase):
    """Microsoft Outlook Calendar API integration."""

    def __init__(self, client_id: str, client_secret: str, tenant_id: str = "common"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.api_base = "https://graph.microsoft.com/v1.0"

    async def create_event(self, event: CalendarEvent, user_token: CalendarToken) -> CalendarEventResult:
        """Create an Outlook Calendar event."""
        try:
            # Build event body
            event_body = {
                "subject": event.title,
                "body": {
                    "contentType": "HTML",
                    "content": event.description or "",
                },
                "start": {
                    "dateTime": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": event.timezone,
                },
                "end": {
                    "dateTime": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": event.timezone,
                },
                "attendees": [
                    {
                        "emailAddress": {"address": email},
                        "type": "required"
                    }
                    for email in event.attendees
                ],
            }

            if event.location:
                event_body["location"] = {"displayName": event.location}

            if event.video_link:
                event_body["body"]["content"] = f"{event.description or ''}<br><br>Video Link: {event.video_link}"
                # Request Teams meeting
                event_body["isOnlineMeeting"] = True
                event_body["onlineMeetingProvider"] = "teamsForBusiness"

            logger.info(f"[SIMULATED] Creating Outlook Calendar event: {event.title}")

            return CalendarEventResult(
                success=True,
                event_id=f"outlook_{secrets.token_hex(12)}",
                event_link=f"https://outlook.office.com/calendar/item/{secrets.token_hex(8)}",
                provider=CalendarProvider.OUTLOOK,
            )

        except Exception as e:
            logger.error(f"Failed to create Outlook Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.OUTLOOK,
            )

    async def update_event(
        self, event_id: str, event: CalendarEvent, user_token: CalendarToken
    ) -> CalendarEventResult:
        """Update an Outlook Calendar event."""
        try:
            logger.info(f"[SIMULATED] Updating Outlook Calendar event: {event_id}")

            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=CalendarProvider.OUTLOOK,
            )

        except Exception as e:
            logger.error(f"Failed to update Outlook Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.OUTLOOK,
            )

    async def delete_event(self, event_id: str, user_token: CalendarToken) -> CalendarEventResult:
        """Delete an Outlook Calendar event."""
        try:
            logger.info(f"[SIMULATED] Deleting Outlook Calendar event: {event_id}")

            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=CalendarProvider.OUTLOOK,
            )

        except Exception as e:
            logger.error(f"Failed to delete Outlook Calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
                provider=CalendarProvider.OUTLOOK,
            )

    async def get_free_busy(
        self,
        email: str,
        start_time: datetime,
        end_time: datetime,
        user_token: CalendarToken,
    ) -> List[Dict[str, datetime]]:
        """Get free/busy information from Outlook Calendar."""
        try:
            logger.info(f"[SIMULATED] Getting free/busy for {email}")

            return []

        except Exception as e:
            logger.error(f"Failed to get free/busy from Outlook Calendar: {e}")
            return []

    async def refresh_token(self, refresh_token: str) -> CalendarToken:
        """Refresh Microsoft OAuth token."""
        return CalendarToken(
            access_token=f"new_access_{secrets.token_hex(16)}",
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            provider=CalendarProvider.OUTLOOK,
        )


# =============================================================================
# Calendar Service (Main Interface)
# =============================================================================

class CalendarService:
    """
    Main calendar service that handles calendar operations across providers.

    Provides a unified interface for:
    - Creating/updating/deleting calendar events
    - Getting free/busy information
    - Managing OAuth tokens
    - Finding optimal meeting times
    """

    def __init__(self):
        from app.config import get_settings
        settings = get_settings()

        self.providers: Dict[CalendarProvider, CalendarProviderBase] = {}

        # Initialize Google Calendar if configured
        google_client_id = getattr(settings, 'google_calendar_client_id', None)
        google_client_secret = getattr(settings, 'google_calendar_client_secret', None)
        if google_client_id and google_client_secret:
            self.providers[CalendarProvider.GOOGLE] = GoogleCalendarProvider(
                client_id=google_client_id,
                client_secret=google_client_secret,
            )

        # Initialize Outlook Calendar if configured
        outlook_client_id = getattr(settings, 'outlook_calendar_client_id', None)
        outlook_client_secret = getattr(settings, 'outlook_calendar_client_secret', None)
        if outlook_client_id and outlook_client_secret:
            self.providers[CalendarProvider.OUTLOOK] = OutlookCalendarProvider(
                client_id=outlook_client_id,
                client_secret=outlook_client_secret,
            )

    def get_available_providers(self) -> List[CalendarProvider]:
        """Get list of configured calendar providers."""
        return list(self.providers.keys())

    async def create_interview_event(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        attendee_emails: List[str],
        location: Optional[str] = None,
        video_link: Optional[str] = None,
        provider: CalendarProvider = CalendarProvider.GOOGLE,
        user_token: Optional[CalendarToken] = None,
    ) -> CalendarEventResult:
        """
        Create a calendar event for an interview.

        Args:
            title: Event title
            description: Event description
            start_time: Start datetime
            end_time: End datetime
            timezone: Timezone for the event
            attendee_emails: List of attendee email addresses
            location: Physical location (optional)
            video_link: Video conferencing link (optional)
            provider: Calendar provider to use
            user_token: OAuth token for the calendar provider

        Returns:
            CalendarEventResult with event ID and link if successful
        """
        if provider == CalendarProvider.NONE:
            return CalendarEventResult(
                success=True,
                event_id=None,
                provider=CalendarProvider.NONE,
            )

        if provider not in self.providers:
            logger.warning(f"Calendar provider {provider} not configured, simulating event creation")
            return CalendarEventResult(
                success=True,
                event_id=f"simulated_{secrets.token_hex(8)}",
                provider=provider,
            )

        event = CalendarEvent(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            location=location,
            video_link=video_link,
            attendees=attendee_emails,
        )

        # Use simulated token if not provided
        if user_token is None:
            user_token = CalendarToken(
                access_token="simulated_token",
                provider=provider,
            )

        return await self.providers[provider].create_event(event, user_token)

    async def update_interview_event(
        self,
        event_id: str,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        attendee_emails: List[str],
        location: Optional[str] = None,
        video_link: Optional[str] = None,
        provider: CalendarProvider = CalendarProvider.GOOGLE,
        user_token: Optional[CalendarToken] = None,
    ) -> CalendarEventResult:
        """Update an existing calendar event."""
        if provider == CalendarProvider.NONE or provider not in self.providers:
            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=provider,
            )

        event = CalendarEvent(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            location=location,
            video_link=video_link,
            attendees=attendee_emails,
        )

        if user_token is None:
            user_token = CalendarToken(
                access_token="simulated_token",
                provider=provider,
            )

        return await self.providers[provider].update_event(event_id, event, user_token)

    async def cancel_interview_event(
        self,
        event_id: str,
        provider: CalendarProvider = CalendarProvider.GOOGLE,
        user_token: Optional[CalendarToken] = None,
    ) -> CalendarEventResult:
        """Cancel/delete a calendar event."""
        if provider == CalendarProvider.NONE or provider not in self.providers:
            return CalendarEventResult(
                success=True,
                event_id=event_id,
                provider=provider,
            )

        if user_token is None:
            user_token = CalendarToken(
                access_token="simulated_token",
                provider=provider,
            )

        return await self.providers[provider].delete_event(event_id, user_token)

    async def find_available_slots(
        self,
        interviewer_emails: List[str],
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        timezone: str = "America/New_York",
        provider: CalendarProvider = CalendarProvider.GOOGLE,
        user_token: Optional[CalendarToken] = None,
        working_hours_start: int = 9,
        working_hours_end: int = 17,
        exclude_weekends: bool = True,
    ) -> List[Dict[str, datetime]]:
        """
        Find available time slots for all interviewers.

        Args:
            interviewer_emails: List of interviewer email addresses
            start_date: Start of date range
            end_date: End of date range
            duration_minutes: Required meeting duration
            timezone: Timezone for the search
            provider: Calendar provider to use
            user_token: OAuth token
            working_hours_start: Start of working hours (hour, 0-23)
            working_hours_end: End of working hours (hour, 0-23)
            exclude_weekends: Whether to exclude Saturday and Sunday

        Returns:
            List of available time slots
        """
        available_slots = []

        # Generate potential slots
        current = start_date.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
        duration = timedelta(minutes=duration_minutes)

        while current < end_date:
            # Skip weekends if requested
            if exclude_weekends and current.weekday() >= 5:
                current = current.replace(hour=working_hours_start) + timedelta(days=1)
                continue

            # Skip outside working hours
            if current.hour >= working_hours_end:
                current = current.replace(hour=working_hours_start) + timedelta(days=1)
                continue

            if current.hour < working_hours_start:
                current = current.replace(hour=working_hours_start)
                continue

            slot_end = current + duration

            # Check if slot fits within working hours
            if slot_end.hour <= working_hours_end or (
                slot_end.hour == working_hours_end and slot_end.minute == 0
            ):
                # In production, check against free/busy data
                available_slots.append({
                    "start_time": current,
                    "end_time": slot_end,
                })

            # Move to next slot (30-minute increments)
            current += timedelta(minutes=30)

        return available_slots

    async def get_combined_availability(
        self,
        user_tokens: Dict[str, CalendarToken],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, List[Dict[str, datetime]]]:
        """
        Get combined free/busy information for multiple users.

        Returns dict mapping email to list of busy periods.
        """
        result = {}

        for email, token in user_tokens.items():
            if token.provider in self.providers:
                busy_periods = await self.providers[token.provider].get_free_busy(
                    email, start_date, end_date, token
                )
                result[email] = busy_periods
            else:
                result[email] = []  # Assume all free if provider not available

        return result


# =============================================================================
# Singleton Instance
# =============================================================================

_calendar_service: Optional[CalendarService] = None


def get_calendar_service() -> CalendarService:
    """Get or create the calendar service singleton."""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service
