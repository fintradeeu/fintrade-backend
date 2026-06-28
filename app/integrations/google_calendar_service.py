import uuid
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict, Any
from urllib.parse import quote
import httpx
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleCalendarError(RuntimeError):
    """Raised when Google Calendar cannot create or update a Meet event."""

class GoogleCalendarService:
    _access_token: Optional[str] = None
    _token_expiry: Optional[datetime] = None

    @classmethod
    async def _get_access_token(cls) -> Optional[str]:
        """Fetch a fresh access token using the refresh token."""
        # Check configuration
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        refresh_token = settings.GOOGLE_REFRESH_TOKEN

        if not all([client_id, client_secret, refresh_token]):
            logger.warn("google_calendar_credentials_missing", 
                        has_id=bool(client_id), 
                        has_secret=bool(client_secret), 
                        has_refresh=bool(refresh_token))
            return None

        # Return cached token if still valid (with 2-minute safety margin)
        if cls._access_token and cls._token_expiry and datetime.now(timezone.utc) < cls._token_expiry - timedelta(minutes=2):
            return cls._access_token

        logger.info("google_calendar_refreshing_token")
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post("https://oauth2.googleapis.com/token", data=payload)
                if res.status_code != 200:
                    logger.error("google_calendar_token_refresh_failed", status_code=res.status_code, body=res.text)
                    raise GoogleCalendarError("Google OAuth token refresh failed. Please reconnect the Google account.")
                
                data = res.json()
                cls._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                cls._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                return cls._access_token
        except Exception as e:
            if isinstance(e, GoogleCalendarError):
                raise
            logger.exception("google_calendar_token_refresh_exception", error=str(e))
            raise GoogleCalendarError("Could not connect to Google OAuth while refreshing the access token.")

    @staticmethod
    def _extract_meeting_link(event_data: Dict[str, Any]) -> Optional[str]:
        meeting_link = event_data.get("hangoutLink")
        if meeting_link:
            return meeting_link

        conf_data = event_data.get("conferenceData", {})
        for entry_point in conf_data.get("entryPoints", []):
            if entry_point.get("entryPointType") == "video" and entry_point.get("uri"):
                return entry_point["uri"]

        return None

    @staticmethod
    def _calendar_id() -> str:
        return quote(settings.GOOGLE_WORKSPACE_EMAIL or "primary", safe="")

    @classmethod
    async def create_event(
        cls, 
        title: str, 
        scheduled_at: datetime, 
        duration_minutes: int, 
        description: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a calendar event with a Google Meet conference.
        Returns a tuple of (event_id, meeting_link).
        """
        token = await cls._get_access_token()
        if not token:
            raise GoogleCalendarError("Google Calendar credentials are not configured.")

        # Format start and end times in ISO 8601 UTC
        # If scheduled_at is naive, assume UTC
        if scheduled_at.tzinfo is None:
            start_dt = scheduled_at.replace(tzinfo=timezone.utc)
        else:
            start_dt = scheduled_at.astimezone(timezone.utc)
            
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        event_body = {
            "summary": title,
            "description": description or "",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "UTC"
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meet-{uuid.uuid4().hex}",
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    }
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"https://www.googleapis.com/calendar/v3/calendars/{cls._calendar_id()}/events?conferenceDataVersion=1",
                    json=event_body,
                    headers=headers
                )
                if res.status_code not in (200, 201):
                    logger.error("google_calendar_event_creation_failed", status_code=res.status_code, body=res.text)
                    raise GoogleCalendarError("Google Calendar rejected the event creation request.")

                event_data = res.json()
                event_id = event_data.get("id")
                meeting_link = cls._extract_meeting_link(event_data)
                if not meeting_link:
                    logger.error("google_calendar_meet_link_missing", event_id=event_id, body=event_data)
                    raise GoogleCalendarError("Google created the event but did not return a Meet link.")

                logger.info("google_calendar_event_created", event_id=event_id, meeting_link=meeting_link)
                return event_id, meeting_link

        except Exception as e:
            if isinstance(e, GoogleCalendarError):
                raise
            logger.exception("google_calendar_event_creation_exception", error=str(e))
            raise GoogleCalendarError("Could not connect to Google Calendar while creating the event.")

    @classmethod
    async def update_event(
        cls, 
        event_id: str, 
        title: str, 
        scheduled_at: datetime, 
        duration_minutes: int, 
        description: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Update an existing Google Calendar event.
        Returns a tuple of (success_boolean, updated_meeting_link).
        """
        token = await cls._get_access_token()
        if not token or not event_id:
            raise GoogleCalendarError("Google Calendar credentials are not configured.")

        if scheduled_at.tzinfo is None:
            start_dt = scheduled_at.replace(tzinfo=timezone.utc)
        else:
            start_dt = scheduled_at.astimezone(timezone.utc)
            
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Retrieve the current event state first to avoid overwriting other details (like meeting links)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 1. Fetch current event
                get_res = await client.get(
                    f"https://www.googleapis.com/calendar/v3/calendars/{cls._calendar_id()}/events/{event_id}",
                    headers=headers
                )
                if get_res.status_code != 200:
                    logger.error("google_calendar_fetch_event_failed", event_id=event_id, status_code=get_res.status_code)
                    raise GoogleCalendarError("Google Calendar could not find the existing lecture event.")
                
                event_data = get_res.json()
                
                # 2. Update values
                event_data["summary"] = title
                event_data["description"] = description or ""
                event_data["start"] = {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": "UTC"
                }
                event_data["end"] = {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": "UTC"
                }

                # 3. Save updates
                put_res = await client.put(
                    f"https://www.googleapis.com/calendar/v3/calendars/{cls._calendar_id()}/events/{event_id}?conferenceDataVersion=1",
                    json=event_data,
                    headers=headers
                )
                if put_res.status_code not in (200, 201):
                    logger.error("google_calendar_event_update_failed", event_id=event_id, status_code=put_res.status_code, body=put_res.text)
                    raise GoogleCalendarError("Google Calendar rejected the event update request.")

                updated_data = put_res.json()
                meeting_link = cls._extract_meeting_link(updated_data)

                logger.info("google_calendar_event_updated", event_id=event_id, meeting_link=meeting_link)
                return True, meeting_link

        except Exception as e:
            if isinstance(e, GoogleCalendarError):
                raise
            logger.exception("google_calendar_event_update_exception", event_id=event_id, error=str(e))
            raise GoogleCalendarError("Could not connect to Google Calendar while updating the event.")

    @classmethod
    async def delete_event(cls, event_id: str) -> bool:
        """
        Delete a Google Calendar event.
        Returns a boolean indicating success.
        """
        token = await cls._get_access_token()
        if not token or not event_id:
            return False

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.delete(
                    f"https://www.googleapis.com/calendar/v3/calendars/{cls._calendar_id()}/events/{event_id}",
                    headers=headers
                )
                if res.status_code not in (200, 204):
                    logger.error("google_calendar_event_deletion_failed", event_id=event_id, status_code=res.status_code, body=res.text)
                    return False

                logger.info("google_calendar_event_deleted", event_id=event_id)
                return True
        except Exception as e:
            logger.exception("google_calendar_event_deletion_exception", event_id=event_id, error=str(e))
            return False
