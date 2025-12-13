"""Google Calendar API client wrapper."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import CalendarAuth
from .config import CalendarsConfig, Settings, get_calendars_config, get_settings
from .models import (
    CalendarEvent,
    CalendarInfo,
    DailyAgenda,
    EventAttendee,
    EventCreateRequest,
    EventDateTime,
    EventUpdateRequest,
    FreeBusyRequest,
    FreeBusyResponse,
    FreeBusySlot,
    WeeklySummary,
)

logger = logging.getLogger(__name__)


class CalendarClient:
    """Google Calendar API client with event management."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        calendars_config: Optional[CalendarsConfig] = None,
    ):
        self.settings = settings or get_settings()
        self.calendars_config = calendars_config or get_calendars_config(self.settings)
        self.auth = CalendarAuth(self.settings)
        self._service = None
        self._timezone = ZoneInfo(self.settings.timezone)

    @property
    def service(self):
        """Get or create Calendar API service."""
        if self._service is None:
            credentials = self.auth.get_credentials()
            self._service = build("calendar", "v3", credentials=credentials)
        return self._service

    def _parse_event(self, event_data: dict, calendar_id: str = "primary") -> CalendarEvent:
        """Parse API event data into CalendarEvent model."""
        start_data = event_data.get("start", {})
        end_data = event_data.get("end", {})

        # Parse start/end times
        start = EventDateTime(
            date_time=date_parser.parse(start_data["dateTime"]) if "dateTime" in start_data else None,
            date=start_data.get("date"),
            time_zone=start_data.get("timeZone"),
        )
        end = EventDateTime(
            date_time=date_parser.parse(end_data["dateTime"]) if "dateTime" in end_data else None,
            date=end_data.get("date"),
            time_zone=end_data.get("timeZone"),
        )

        # Parse attendees
        attendees = []
        for att in event_data.get("attendees", []):
            attendees.append(
                EventAttendee(
                    email=att.get("email", ""),
                    display_name=att.get("displayName"),
                    response_status=att.get("responseStatus"),
                    organizer=att.get("organizer", False),
                    self_=att.get("self", False),
                )
            )

        # Categorize event
        summary = event_data.get("summary", "")
        description = event_data.get("description", "")
        category = self.calendars_config.categorize_event(calendar_id, summary, description)

        return CalendarEvent(
            id=event_data.get("id", ""),
            summary=summary,
            description=description,
            location=event_data.get("location"),
            start=start,
            end=end,
            status=event_data.get("status", "confirmed"),
            html_link=event_data.get("htmlLink"),
            created=date_parser.parse(event_data["created"]) if "created" in event_data else None,
            updated=date_parser.parse(event_data["updated"]) if "updated" in event_data else None,
            creator_email=event_data.get("creator", {}).get("email"),
            organizer_email=event_data.get("organizer", {}).get("email"),
            attendees=attendees,
            recurrence=event_data.get("recurrence"),
            recurring_event_id=event_data.get("recurringEventId"),
            calendar_id=calendar_id,
            category=category.key if category else None,
            color_id=event_data.get("colorId"),
            visibility=event_data.get("visibility"),
            conference_data=event_data.get("conferenceData"),
        )

    async def list_calendars(self) -> list[CalendarInfo]:
        """List all available calendars."""
        try:
            result = self.service.calendarList().list().execute()
            calendars = []

            for cal in result.get("items", []):
                calendars.append(
                    CalendarInfo(
                        id=cal.get("id", ""),
                        summary=cal.get("summary", ""),
                        description=cal.get("description"),
                        time_zone=cal.get("timeZone"),
                        color_id=cal.get("colorId"),
                        background_color=cal.get("backgroundColor"),
                        foreground_color=cal.get("foregroundColor"),
                        access_role=cal.get("accessRole"),
                        primary=cal.get("primary", False),
                        selected=cal.get("selected", True),
                    )
                )

            return calendars
        except HttpError as e:
            logger.error(f"Failed to list calendars: {e}")
            raise

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50,
        query: Optional[str] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> list[CalendarEvent]:
        """List events from a calendar."""
        try:
            # Default to next 7 days if no time range specified
            if time_min is None:
                time_min = datetime.now(self._timezone)
            if time_max is None:
                time_max = time_min + timedelta(days=7)

            # Ensure timezone awareness
            if time_min.tzinfo is None:
                time_min = time_min.replace(tzinfo=self._timezone)
            if time_max.tzinfo is None:
                time_max = time_max.replace(tzinfo=self._timezone)

            params = {
                "calendarId": calendar_id,
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "maxResults": max_results,
                "singleEvents": single_events,
                "orderBy": order_by if single_events else None,
            }

            if query:
                params["q"] = query

            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            result = self.service.events().list(**params).execute()

            events = []
            for event_data in result.get("items", []):
                events.append(self._parse_event(event_data, calendar_id))

            return events
        except HttpError as e:
            logger.error(f"Failed to list events: {e}")
            raise

    async def search_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 20,
    ) -> list[CalendarEvent]:
        """Search events by text query."""
        return await self.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            query=query,
        )

    async def get_event(self, event_id: str, calendar_id: str = "primary") -> CalendarEvent:
        """Get a specific event by ID."""
        try:
            event_data = (
                self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            )
            return self._parse_event(event_data, calendar_id)
        except HttpError as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            raise

    async def create_event(self, request: EventCreateRequest) -> CalendarEvent:
        """Create a new calendar event."""
        try:
            # Build event body
            event_body = {
                "summary": request.summary,
            }

            if request.description:
                event_body["description"] = request.description
            if request.location:
                event_body["location"] = request.location

            # Set start/end times
            tz = request.time_zone or self.settings.timezone

            if request.all_day:
                event_body["start"] = {"date": request.start_time.strftime("%Y-%m-%d")}
                end_time = request.end_time or (request.start_time + timedelta(days=1))
                event_body["end"] = {"date": end_time.strftime("%Y-%m-%d")}
            else:
                event_body["start"] = {
                    "dateTime": request.start_time.isoformat(),
                    "timeZone": tz,
                }
                end_time = request.end_time or (
                    request.start_time + timedelta(minutes=request.duration_minutes)
                )
                event_body["end"] = {
                    "dateTime": end_time.isoformat(),
                    "timeZone": tz,
                }

            # Add attendees
            if request.attendees:
                event_body["attendees"] = [{"email": email} for email in request.attendees]

            # Add reminders
            if request.reminders:
                event_body["reminders"] = {
                    "useDefault": False,
                    "overrides": [
                        {"method": r.method, "minutes": r.minutes} for r in request.reminders
                    ],
                }

            # Add recurrence
            if request.recurrence:
                event_body["recurrence"] = [request.recurrence]

            # Set visibility
            if request.visibility:
                event_body["visibility"] = request.visibility

            result = (
                self.service.events()
                .insert(
                    calendarId=request.calendar_id,
                    body=event_body,
                    sendNotifications=request.send_notifications,
                )
                .execute()
            )

            logger.info(f"Created event: {result.get('id')}")
            return self._parse_event(result, request.calendar_id)
        except HttpError as e:
            logger.error(f"Failed to create event: {e}")
            raise

    async def update_event(
        self,
        event_id: str,
        request: EventUpdateRequest,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        """Update an existing event."""
        try:
            # Get current event
            current = (
                self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            )

            # Update fields
            if request.summary is not None:
                current["summary"] = request.summary
            if request.description is not None:
                current["description"] = request.description
            if request.location is not None:
                current["location"] = request.location

            if request.start_time is not None:
                if request.all_day:
                    current["start"] = {"date": request.start_time.strftime("%Y-%m-%d")}
                else:
                    current["start"] = {
                        "dateTime": request.start_time.isoformat(),
                        "timeZone": self.settings.timezone,
                    }

            if request.end_time is not None:
                if request.all_day:
                    current["end"] = {"date": request.end_time.strftime("%Y-%m-%d")}
                else:
                    current["end"] = {
                        "dateTime": request.end_time.isoformat(),
                        "timeZone": self.settings.timezone,
                    }

            if request.attendees is not None:
                current["attendees"] = [{"email": email} for email in request.attendees]

            if request.visibility is not None:
                current["visibility"] = request.visibility

            result = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=current,
                    sendNotifications=request.send_notifications,
                )
                .execute()
            )

            logger.info(f"Updated event: {event_id}")
            return self._parse_event(result, calendar_id)
        except HttpError as e:
            logger.error(f"Failed to update event {event_id}: {e}")
            raise

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        send_notifications: bool = True,
    ) -> bool:
        """Delete an event."""
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendNotifications=send_notifications,
            ).execute()
            logger.info(f"Deleted event: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            raise

    async def get_free_busy(self, request: FreeBusyRequest) -> list[FreeBusyResponse]:
        """Get free/busy information for calendars."""
        try:
            body = {
                "timeMin": request.time_min.isoformat(),
                "timeMax": request.time_max.isoformat(),
                "items": [{"id": cal_id} for cal_id in request.calendar_ids],
            }

            if request.time_zone:
                body["timeZone"] = request.time_zone

            result = self.service.freebusy().query(body=body).execute()

            responses = []
            for cal_id, cal_data in result.get("calendars", {}).items():
                busy_slots = []
                for slot in cal_data.get("busy", []):
                    busy_slots.append(
                        FreeBusySlot(
                            start=date_parser.parse(slot["start"]),
                            end=date_parser.parse(slot["end"]),
                        )
                    )
                responses.append(FreeBusyResponse(calendar_id=cal_id, busy=busy_slots))

            return responses
        except HttpError as e:
            logger.error(f"Failed to get free/busy: {e}")
            raise

    async def get_daily_agenda(
        self,
        date: Optional[datetime] = None,
        calendar_ids: Optional[list[str]] = None,
    ) -> DailyAgenda:
        """Get daily agenda for specified date."""
        if date is None:
            date = datetime.now(self._timezone)

        # Set to start/end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        calendar_ids = calendar_ids or ["primary"]

        all_events = []
        for cal_id in calendar_ids:
            events = await self.list_events(
                calendar_id=cal_id,
                time_min=start_of_day,
                time_max=end_of_day,
            )
            all_events.extend(events)

        # Sort by start time
        all_events.sort(key=lambda e: e.start_datetime or datetime.min.replace(tzinfo=self._timezone))

        # Separate all-day and timed events
        all_day_events = [e for e in all_events if e.is_all_day]
        timed_events = [e for e in all_events if not e.is_all_day]

        # Group by category
        categories: dict[str, list[CalendarEvent]] = {}
        for event in all_events:
            cat = event.category or "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(event)

        return DailyAgenda(
            date=start_of_day.strftime("%Y-%m-%d"),
            events=all_events,
            event_count=len(all_events),
            all_day_events=all_day_events,
            timed_events=timed_events,
            categories=categories,
        )

    async def get_weekly_summary(
        self,
        start_date: Optional[datetime] = None,
        calendar_ids: Optional[list[str]] = None,
    ) -> WeeklySummary:
        """Get weekly summary starting from specified date."""
        if start_date is None:
            start_date = datetime.now(self._timezone)
            # Go to start of week (Monday)
            start_date = start_date - timedelta(days=start_date.weekday())

        start_of_week = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=7)

        calendar_ids = calendar_ids or ["primary"]

        all_events = []
        for cal_id in calendar_ids:
            events = await self.list_events(
                calendar_id=cal_id,
                time_min=start_of_week,
                time_max=end_of_week,
            )
            all_events.extend(events)

        # Group by day
        events_by_day: dict[str, list[CalendarEvent]] = {}
        for event in all_events:
            if event.start_datetime:
                day = event.start_datetime.strftime("%Y-%m-%d")
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append(event)

        # Find busiest day
        busiest_day = None
        max_events = 0
        for day, events in events_by_day.items():
            if len(events) > max_events:
                max_events = len(events)
                busiest_day = day

        # Count by category
        category_counts: dict[str, int] = {}
        for event in all_events:
            cat = event.category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return WeeklySummary(
            week_start=start_of_week.strftime("%Y-%m-%d"),
            week_end=(end_of_week - timedelta(days=1)).strftime("%Y-%m-%d"),
            total_events=len(all_events),
            events_by_day=events_by_day,
            busiest_day=busiest_day,
            categories=category_counts,
        )

    async def find_free_slots(
        self,
        time_min: datetime,
        time_max: datetime,
        duration_minutes: int = 60,
        working_hours_start: int = 9,
        working_hours_end: int = 17,
        calendar_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """Find free time slots within working hours.
        
        Args:
            time_min: Start of search range
            time_max: End of search range
            duration_minutes: Required slot duration
            working_hours_start: Start of working hours (0-23)
            working_hours_end: End of working hours (1-24)
            calendar_ids: Calendars to check (defaults to primary)
            
        Returns:
            List of dicts with 'start' and 'end' datetime objects
        """
        calendar_ids = calendar_ids or ["primary"]
        
        # Get all events in the range
        all_events = []
        for cal_id in calendar_ids:
            events = await self.list_events(
                calendar_id=cal_id,
                time_min=time_min,
                time_max=time_max,
                max_results=250,
            )
            all_events.extend(events)
        
        # Sort by start time
        all_events.sort(key=lambda e: e.start_datetime or datetime.min.replace(tzinfo=self._timezone))
        
        # Find free slots
        free_slots = []
        current = time_min
        if current.tzinfo is None:
            current = current.replace(tzinfo=self._timezone)
        
        while current < time_max:
            # Move to working hours if needed
            if current.hour < working_hours_start:
                current = current.replace(hour=working_hours_start, minute=0, second=0)
            elif current.hour >= working_hours_end:
                # Move to next day
                current = (current + timedelta(days=1)).replace(
                    hour=working_hours_start, minute=0, second=0
                )
                continue
            
            # Find end of current working period
            work_end = current.replace(hour=working_hours_end, minute=0, second=0)
            if work_end > time_max:
                work_end = time_max
            
            # Check for events blocking this slot
            slot_start = current
            for event in all_events:
                event_start = event.start_datetime
                event_end = event.end_datetime
                
                if event_start is None or event_end is None:
                    continue
                    
                # Event timezone handling
                if event_start.tzinfo is None:
                    event_start = event_start.replace(tzinfo=self._timezone)
                if event_end.tzinfo is None:
                    event_end = event_end.replace(tzinfo=self._timezone)
                
                # Skip events outside current slot range
                if event_end <= slot_start or event_start >= work_end:
                    continue
                
                # Calculate free time before this event
                if event_start > slot_start:
                    slot_duration = (event_start - slot_start).total_seconds() / 60
                    if slot_duration >= duration_minutes:
                        free_slots.append({
                            "start": slot_start,
                            "end": event_start,
                        })
                
                # Move past this event
                slot_start = max(slot_start, event_end)
            
            # Check remaining time in work period
            if slot_start < work_end:
                remaining = (work_end - slot_start).total_seconds() / 60
                if remaining >= duration_minutes:
                    free_slots.append({
                        "start": slot_start,
                        "end": work_end,
                    })
            
            # Move to next day
            current = (current + timedelta(days=1)).replace(
                hour=working_hours_start, minute=0, second=0
            )
        
        return free_slots
