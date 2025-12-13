"""MCP Google Calendar Server.

A Model Context Protocol server for Google Calendar integration.
"""

__version__ = "0.1.0"

from .auth import CalendarAuth
from .calendar_client import CalendarClient
from .config import CalendarsConfig, Settings, get_calendars_config, get_settings
from .models import (
    Attendee,
    CalendarInfo,
    DailySummary,
    Event,
    EventDateTime,
    EventsResponse,
    WeekSummary,
)

__all__ = [
    "CalendarAuth",
    "CalendarClient",
    "CalendarsConfig",
    "Settings",
    "get_calendars_config",
    "get_settings",
    "Attendee",
    "CalendarInfo",
    "DailySummary",
    "Event",
    "EventDateTime",
    "EventsResponse",
    "WeekSummary",
]