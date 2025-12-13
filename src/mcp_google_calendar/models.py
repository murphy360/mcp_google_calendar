"""Pydantic models for Google Calendar data."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventDateTime(BaseModel):
    """Event date/time model."""

    date_time: Optional[datetime] = Field(None, alias="dateTime")
    date: Optional[str] = None  # For all-day events (YYYY-MM-DD)
    time_zone: Optional[str] = Field(None, alias="timeZone")

    class Config:
        populate_by_name = True


class EventAttendee(BaseModel):
    """Event attendee model."""

    email: str
    display_name: Optional[str] = Field(None, alias="displayName")
    response_status: Optional[str] = Field(None, alias="responseStatus")
    organizer: bool = False
    self_: bool = Field(False, alias="self")

    class Config:
        populate_by_name = True


class EventReminder(BaseModel):
    """Event reminder model."""

    method: str  # 'email' or 'popup'
    minutes: int


class CalendarEvent(BaseModel):
    """Calendar event model."""

    id: str
    summary: str = ""
    description: Optional[str] = None
    location: Optional[str] = None
    start: EventDateTime
    end: EventDateTime
    status: str = "confirmed"
    html_link: Optional[str] = Field(None, alias="htmlLink")
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    creator_email: Optional[str] = None
    organizer_email: Optional[str] = None
    attendees: list[EventAttendee] = []
    recurrence: Optional[list[str]] = None
    recurring_event_id: Optional[str] = Field(None, alias="recurringEventId")
    calendar_id: Optional[str] = None
    category: Optional[str] = None
    color_id: Optional[str] = Field(None, alias="colorId")
    visibility: Optional[str] = None
    conference_data: Optional[dict] = Field(None, alias="conferenceData")

    class Config:
        populate_by_name = True

    @property
    def is_all_day(self) -> bool:
        """Check if event is all-day."""
        return self.start.date is not None

    @property
    def start_datetime(self) -> datetime | None:
        """Get start as datetime."""
        if self.start.date_time:
            return self.start.date_time
        if self.start.date:
            return datetime.fromisoformat(self.start.date)
        return None

    @property
    def end_datetime(self) -> datetime | None:
        """Get end as datetime."""
        if self.end.date_time:
            return self.end.date_time
        if self.end.date:
            return datetime.fromisoformat(self.end.date)
        return None

    @property
    def duration_minutes(self) -> int | None:
        """Get duration in minutes."""
        start = self.start_datetime
        end = self.end_datetime
        if start and end:
            return int((end - start).total_seconds() / 60)
        return None

    @property
    def meeting_link(self) -> str | None:
        """Get video meeting link if available."""
        if self.conference_data:
            entry_points = self.conference_data.get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    return ep.get("uri")
        return None


class CalendarInfo(BaseModel):
    """Calendar information model."""

    id: str
    summary: str
    description: Optional[str] = None
    time_zone: Optional[str] = Field(None, alias="timeZone")
    color_id: Optional[str] = Field(None, alias="colorId")
    background_color: Optional[str] = Field(None, alias="backgroundColor")
    foreground_color: Optional[str] = Field(None, alias="foregroundColor")
    access_role: Optional[str] = Field(None, alias="accessRole")
    primary: bool = False
    selected: bool = True

    class Config:
        populate_by_name = True


class EventCreateRequest(BaseModel):
    """Request model for creating an event."""

    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: int = 60
    all_day: bool = False
    calendar_id: str = "primary"
    attendees: list[str] = []  # List of email addresses
    reminders: list[EventReminder] = []
    recurrence: Optional[str] = None  # RRULE string
    time_zone: Optional[str] = None
    visibility: Optional[str] = None  # 'default', 'public', 'private'
    send_notifications: bool = True


class EventUpdateRequest(BaseModel):
    """Request model for updating an event."""

    summary: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    attendees: Optional[list[str]] = None
    reminders: Optional[list[EventReminder]] = None
    visibility: Optional[str] = None
    send_notifications: bool = True


class FreeBusyRequest(BaseModel):
    """Request model for free/busy query."""

    time_min: datetime
    time_max: datetime
    calendar_ids: list[str] = ["primary"]
    time_zone: Optional[str] = None


class FreeBusySlot(BaseModel):
    """Free/busy time slot."""

    start: datetime
    end: datetime


class FreeBusyResponse(BaseModel):
    """Free/busy query response."""

    calendar_id: str
    busy: list[FreeBusySlot]


class DailyAgenda(BaseModel):
    """Daily agenda summary."""

    date: str
    events: list[CalendarEvent]
    event_count: int
    all_day_events: list[CalendarEvent]
    timed_events: list[CalendarEvent]
    categories: dict[str, list[CalendarEvent]]

    @property
    def has_events(self) -> bool:
        """Check if there are any events."""
        return self.event_count > 0


class WeeklySummary(BaseModel):
    """Weekly calendar summary."""

    week_start: str
    week_end: str
    total_events: int
    events_by_day: dict[str, list[CalendarEvent]]
    busiest_day: Optional[str]
    categories: dict[str, int]
