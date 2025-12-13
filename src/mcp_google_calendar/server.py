"""MCP Server implementation for Google Calendar.

This module implements the MCP server with a factory pattern to create
fresh server instances for each connection, ensuring proper session isolation.

Tool schemas are designed to be compatible with Google Gemini's strict
schema requirements - using explicit types with no defaults in required fields.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from .calendar_client import CalendarClient
from .config import Settings, get_calendars_config, get_settings
from .models import EventCreateRequest, EventUpdateRequest, FreeBusyRequest

logger = logging.getLogger(__name__)

# Global client instance (shared across server instances)
_calendar_client: CalendarClient | None = None


def get_calendar_client() -> CalendarClient:
    """Get or create Calendar client instance."""
    global _calendar_client
    if _calendar_client is None:
        settings = get_settings()
        calendars_config = get_calendars_config(settings)
        _calendar_client = CalendarClient(settings, calendars_config)
    return _calendar_client


def format_event_time(dt: datetime | None, tz: ZoneInfo) -> str:
    """Format a datetime for display in the specified timezone."""
    if dt is None:
        return "Unknown time"
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz)
    return dt.strftime("%a %b %d, %I:%M %p")


def format_time_only(dt: datetime | None, tz: ZoneInfo) -> str:
    """Format just the time portion in the specified timezone."""
    if dt is None:
        return "TBD"
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz)
    return dt.strftime("%I:%M %p")


# ============================================================================
# TOOL DEFINITIONS (Gemini-compatible schemas)
# ============================================================================

CALENDAR_TOOLS = [
    Tool(
        name="calendar_get_current_time",
        description="""Get the current date and time in the user's timezone.

Use this tool to understand what 'today', 'tomorrow', 'this week' means
before making calendar queries. Returns current time, date, and reference
dates for the week.""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="calendar_list_events",
        description="""List upcoming calendar events within a date range.

Returns events from a specific calendar with details including title,
time, location, and meeting links. Use days_ahead to control how far
into the future to search.""",
        inputSchema={
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days ahead to look for events. Use 7 for one week, 30 for one month.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "The calendar ID to query. Use 'primary' for the main calendar.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return. Recommended: 10-50.",
                },
            },
        },
    ),
    Tool(
        name="calendar_search",
        description="""Search calendar events by text query.

Searches event titles, descriptions, and locations for matching text.
Can search both past and future events by specifying days_back and days_ahead.""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search text to find in events. Searches titles, descriptions, and locations.",
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days ahead to search. Use 30 for one month forward.",
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days back to search. Use 0 for future only, 30 for one month back.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return.",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="calendar_get_event",
        description="""Get detailed information about a specific calendar event.

Returns full event details including title, description, start/end times,
location, attendees, and meeting links. Requires the event ID.""",
        inputSchema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The unique event ID. Obtain this from calendar_list_events or calendar_search.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "The calendar ID where the event exists. Use 'primary' for the main calendar.",
                },
            },
            "required": ["event_id"],
        },
    ),
    Tool(
        name="calendar_create_event",
        description="""Create a new calendar event.

Creates an event with the specified details. At minimum, requires a
title and start time. End time defaults to one hour after start if not provided.""",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "The event title/summary. This is what appears on the calendar.",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g., '2024-12-15T14:00:00' or '2024-12-15T14:00:00-05:00').",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format. If not provided, defaults to start time plus one hour.",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description or notes for the event.",
                },
                "location": {
                    "type": "string",
                    "description": "Physical address or location name for the event.",
                },
                "attendees": {
                    "type": "string",
                    "description": "Comma-separated list of attendee email addresses (e.g., 'user1@example.com,user2@example.com').",
                },
                "all_day": {
                    "type": "boolean",
                    "description": "Set to true for all-day events. When true, only the date portion of start_time is used.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "The calendar ID to create the event in. Use 'primary' for the main calendar.",
                },
            },
            "required": ["summary", "start_time"],
        },
    ),
    Tool(
        name="calendar_update_event",
        description="""Update an existing calendar event.

Modifies one or more fields of an existing event. Only provide the
fields you want to change; unspecified fields remain unchanged.""",
        inputSchema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The unique event ID to update. Obtain this from calendar_list_events or calendar_search.",
                },
                "summary": {
                    "type": "string",
                    "description": "New event title/summary.",
                },
                "start_time": {
                    "type": "string",
                    "description": "New start time in ISO 8601 format.",
                },
                "end_time": {
                    "type": "string",
                    "description": "New end time in ISO 8601 format.",
                },
                "description": {
                    "type": "string",
                    "description": "New event description.",
                },
                "location": {
                    "type": "string",
                    "description": "New event location.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "The calendar ID where the event exists. Use 'primary' for the main calendar.",
                },
            },
            "required": ["event_id"],
        },
    ),
    Tool(
        name="calendar_delete_event",
        description="""Delete a calendar event.

Permanently removes an event from the calendar. Optionally notifies
attendees about the cancellation.""",
        inputSchema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The unique event ID to delete.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "The calendar ID where the event exists. Use 'primary' for the main calendar.",
                },
                "notify_attendees": {
                    "type": "boolean",
                    "description": "Set to true to send cancellation emails to attendees, false to delete silently.",
                },
            },
            "required": ["event_id"],
        },
    ),
    Tool(
        name="calendar_daily_agenda",
        description="""Get the agenda for a specific day with all events.

Returns a formatted summary of all events for the specified date,
organized by all-day events and timed events. Useful for daily briefings.""",
        inputSchema={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (e.g., '2024-12-15'). If not provided, uses today's date.",
                },
                "calendar_ids": {
                    "type": "string",
                    "description": "Comma-separated list of calendar IDs to include (e.g., 'primary,work@group.calendar.google.com'). If not provided, includes all calendars.",
                },
            },
        },
    ),
    Tool(
        name="calendar_weekly_summary",
        description="""Get a summary of events for the upcoming 7 days.

Returns a week overview with events organized by day, total event count,
and busiest day indicator. Useful for weekly planning.""",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format. If not provided, starts from today.",
                },
                "calendar_ids": {
                    "type": "string",
                    "description": "Comma-separated list of calendar IDs to include. If not provided, includes all calendars.",
                },
            },
        },
    ),
    Tool(
        name="calendar_list_calendars",
        description="""List all available calendars.

Returns a list of all calendars accessible to the authenticated user,
including their IDs, names, and whether they are the primary calendar.""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="calendar_free_busy",
        description="""Check free/busy status for a time range.

Returns busy time slots within the specified range for one or more calendars.
Useful for finding available meeting times.""",
        inputSchema={
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "Start of the time range in ISO 8601 format.",
                },
                "end_time": {
                    "type": "string",
                    "description": "End of the time range in ISO 8601 format.",
                },
                "calendar_ids": {
                    "type": "string",
                    "description": "Comma-separated list of calendar IDs to check. If not provided, checks 'primary'.",
                },
            },
            "required": ["start_time", "end_time"],
        },
    ),
]


# ============================================================================
# TOOL HANDLERS
# ============================================================================


async def handle_get_current_time(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_get_current_time tool."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz)
    
    lines = [
        "🕐 Current Date & Time Information:\n",
        f"Timezone: {settings.timezone}",
        f"Current Date: {now.strftime('%A, %B %d, %Y')}",
        f"Current Time: {now.strftime('%I:%M %p')}",
        f"ISO Format: {now.isoformat()}",
        "",
        "📅 Reference Dates:",
        f"Today: {now.strftime('%Y-%m-%d')}",
        f"Tomorrow: {(now + timedelta(days=1)).strftime('%Y-%m-%d')}",
        f"This week ends: {(now + timedelta(days=(6 - now.weekday()))).strftime('%Y-%m-%d')}",
        f"Next week starts: {(now + timedelta(days=(7 - now.weekday()))).strftime('%Y-%m-%d')}",
    ]
    
    return [TextContent(type="text", text="\n".join(lines))]


async def handle_list_events(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_list_events tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    days_ahead = arguments.get("days_ahead", 7)
    calendar_id = arguments.get("calendar_id", "primary")
    max_results = arguments.get("max_results", 20)

    time_min = datetime.now(tz)
    time_max = time_min + timedelta(days=days_ahead)

    events = await client.list_events(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )

    if not events:
        return [TextContent(type="text", text="No upcoming events found.")]

    lines = [f"📅 Upcoming Events ({len(events)} events):\n"]
    for event in events:
        if event.is_all_day:
            time_str = "All day"
        else:
            time_str = format_event_time(event.start_datetime, tz)

        lines.append(f"• {event.summary}")
        lines.append(f"  📆 {time_str}")
        if event.location:
            lines.append(f"  📍 {event.location}")
        if event.meeting_link:
            lines.append(f"  🔗 {event.meeting_link}")
        lines.append(f"  ID: {event.id}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_search(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_search tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    query = arguments["query"]
    days_ahead = arguments.get("days_ahead", 30)
    days_back = arguments.get("days_back", 0)
    max_results = arguments.get("max_results", 20)

    time_min = datetime.now(tz) - timedelta(days=days_back)
    time_max = datetime.now(tz) + timedelta(days=days_ahead)

    events = await client.search_events(
        query=query,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )

    if not events:
        return [TextContent(type="text", text=f"No events found matching '{query}'.")]

    lines = [f"🔍 Search Results for '{query}' ({len(events)} events):\n"]
    for event in events:
        if event.is_all_day:
            time_str = "All day"
        else:
            time_str = format_event_time(event.start_datetime, tz)
        lines.append(f"• {event.summary}")
        lines.append(f"  📆 {time_str}")
        lines.append(f"  ID: {event.id}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_get_event(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_get_event tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    event_id = arguments["event_id"]
    calendar_id = arguments.get("calendar_id", "primary")

    event = await client.get_event(event_id, calendar_id)

    lines = [f"📅 Event Details:\n"]
    lines.append(f"Title: {event.summary}")
    if event.description:
        lines.append(f"Description: {event.description}")

    start = event.start_datetime
    end = event.end_datetime
    if event.is_all_day:
        lines.append(f"Time: All day ({event.start.date})")
    elif start and end:
        start_local = start.astimezone(tz) if start.tzinfo else start
        end_local = end.astimezone(tz) if end.tzinfo else end
        lines.append(f"Start: {start_local.strftime('%a %b %d, %Y %I:%M %p')}")
        lines.append(f"End: {end_local.strftime('%a %b %d, %Y %I:%M %p')}")
        if event.duration_minutes:
            lines.append(f"Duration: {event.duration_minutes} minutes")

    if event.location:
        lines.append(f"Location: {event.location}")
    if event.meeting_link:
        lines.append(f"Meeting Link: {event.meeting_link}")
    if event.attendees:
        lines.append(f"Attendees: {len(event.attendees)}")
        for att in event.attendees[:5]:
            status = att.response_status or "unknown"
            lines.append(f"  • {att.email} ({status})")
    if event.html_link:
        lines.append(f"Google Calendar Link: {event.html_link}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_create_event(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_create_event tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    start_time = datetime.fromisoformat(arguments["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=tz)

    end_time = None
    if arguments.get("end_time"):
        end_time = datetime.fromisoformat(arguments["end_time"])
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=tz)

    # Parse attendees from comma-separated string
    attendees_str = arguments.get("attendees", "")
    attendees = [a.strip() for a in attendees_str.split(",") if a.strip()] if attendees_str else []

    request = EventCreateRequest(
        summary=arguments["summary"],
        start_time=start_time,
        end_time=end_time,
        description=arguments.get("description"),
        location=arguments.get("location"),
        attendees=attendees,
        all_day=arguments.get("all_day", False),
        calendar_id=arguments.get("calendar_id", "primary"),
    )

    event = await client.create_event(request)

    return [
        TextContent(
            type="text",
            text=f"✅ Event created successfully!\n\nTitle: {event.summary}\nID: {event.id}\nLink: {event.html_link}",
        )
    ]


async def handle_update_event(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_update_event tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    event_id = arguments["event_id"]
    calendar_id = arguments.get("calendar_id", "primary")

    start_time = None
    if arguments.get("start_time"):
        start_time = datetime.fromisoformat(arguments["start_time"])
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=tz)

    end_time = None
    if arguments.get("end_time"):
        end_time = datetime.fromisoformat(arguments["end_time"])
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=tz)

    request = EventUpdateRequest(
        summary=arguments.get("summary"),
        description=arguments.get("description"),
        location=arguments.get("location"),
        start_time=start_time,
        end_time=end_time,
    )

    event = await client.update_event(event_id, request, calendar_id)

    return [
        TextContent(
            type="text",
            text=f"✅ Event updated successfully!\n\nTitle: {event.summary}\nID: {event.id}",
        )
    ]


async def handle_delete_event(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_delete_event tool."""
    client = get_calendar_client()
    
    event_id = arguments["event_id"]
    calendar_id = arguments.get("calendar_id", "primary")
    notify = arguments.get("notify_attendees", True)

    await client.delete_event(event_id, calendar_id, notify)

    return [TextContent(type="text", text=f"✅ Event deleted successfully (ID: {event_id})")]


async def handle_daily_agenda(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_daily_agenda tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    date = None
    if arguments.get("date"):
        date = datetime.strptime(arguments["date"], "%Y-%m-%d").replace(tzinfo=tz)

    # Parse calendar_ids from comma-separated string
    calendar_ids_str = arguments.get("calendar_ids", "")
    if calendar_ids_str:
        calendar_ids = [cid.strip() for cid in calendar_ids_str.split(",") if cid.strip()]
    else:
        # Get all available calendars
        all_calendars = await client.list_calendars()
        calendar_ids = [cal.id for cal in all_calendars]

    agenda = await client.get_daily_agenda(date, calendar_ids=calendar_ids)

    if not agenda.has_events:
        return [TextContent(type="text", text=f"📅 No events scheduled for {agenda.date}")]

    lines = [f"📅 Daily Agenda for {agenda.date}\n"]
    lines.append(f"Total events: {agenda.event_count}\n")

    if agenda.all_day_events:
        lines.append("🌅 All-Day Events:")
        for event in agenda.all_day_events:
            lines.append(f"  • {event.summary}")
        lines.append("")

    if agenda.timed_events:
        lines.append("⏰ Scheduled Events:")
        for event in agenda.timed_events:
            time_str = format_time_only(event.start_datetime, tz)
            lines.append(f"  • {time_str} - {event.summary}")
            if event.location:
                lines.append(f"    📍 {event.location}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_weekly_summary(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_weekly_summary tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    start_date = None
    if arguments.get("start_date"):
        start_date = datetime.strptime(arguments["start_date"], "%Y-%m-%d").replace(tzinfo=tz)

    # Parse calendar_ids from comma-separated string
    calendar_ids_str = arguments.get("calendar_ids", "")
    if calendar_ids_str:
        calendar_ids = [cid.strip() for cid in calendar_ids_str.split(",") if cid.strip()]
    else:
        # Get all available calendars
        all_calendars = await client.list_calendars()
        calendar_ids = [cal.id for cal in all_calendars]

    summary = await client.get_weekly_summary(start_date, calendar_ids=calendar_ids)

    lines = [f"📅 Weekly Summary ({summary.week_start} to {summary.week_end})\n"]
    lines.append(f"Total events: {summary.total_events}")
    if summary.busiest_day:
        lines.append(f"Busiest day: {summary.busiest_day}")
    lines.append("")

    for day, events in sorted(summary.events_by_day.items()):
        day_name = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %b %d")
        lines.append(f"📆 {day_name} ({len(events)} events)")
        for event in events[:5]:
            if event.is_all_day:
                lines.append(f"  • 🌅 All day - {event.summary}")
            else:
                time_str = format_time_only(event.start_datetime, tz)
                lines.append(f"  • {time_str} - {event.summary}")
        if len(events) > 5:
            lines.append(f"  ... and {len(events) - 5} more")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_list_calendars(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_list_calendars tool."""
    client = get_calendar_client()
    
    calendars = await client.list_calendars()

    lines = ["📚 Available Calendars:\n"]
    for cal in calendars:
        primary = " (Primary)" if cal.primary else ""
        lines.append(f"• {cal.summary}{primary}")
        lines.append(f"  ID: {cal.id}")
        if cal.description:
            lines.append(f"  Description: {cal.description}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_free_busy(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle calendar_free_busy tool."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    
    start_time = datetime.fromisoformat(arguments["start_time"])
    end_time = datetime.fromisoformat(arguments["end_time"])

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=tz)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=tz)

    # Parse calendar_ids from comma-separated string
    calendar_ids_str = arguments.get("calendar_ids", "")
    if calendar_ids_str:
        calendar_ids = [cid.strip() for cid in calendar_ids_str.split(",") if cid.strip()]
    else:
        calendar_ids = ["primary"]

    request = FreeBusyRequest(
        time_min=start_time,
        time_max=end_time,
        calendar_ids=calendar_ids,
    )

    results = await client.get_free_busy(request)

    start_display = start_time.astimezone(tz).strftime('%b %d %I:%M %p')
    end_display = end_time.astimezone(tz).strftime('%b %d %I:%M %p')
    lines = [f"📊 Free/Busy Status ({start_display} - {end_display})\n"]

    for result in results:
        lines.append(f"Calendar: {result.calendar_id}")
        if not result.busy:
            lines.append("  ✅ Free during this time")
        else:
            lines.append(f"  ❌ Busy ({len(result.busy)} conflicts):")
            for slot in result.busy[:5]:
                slot_start = slot.start.astimezone(tz) if slot.start.tzinfo else slot.start
                slot_end = slot.end.astimezone(tz) if slot.end.tzinfo else slot.end
                lines.append(
                    f"    • {slot_start.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}"
                )
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


# Tool handler dispatch table
TOOL_HANDLERS = {
    "calendar_get_current_time": handle_get_current_time,
    "calendar_list_events": handle_list_events,
    "calendar_search": handle_search,
    "calendar_get_event": handle_get_event,
    "calendar_create_event": handle_create_event,
    "calendar_update_event": handle_update_event,
    "calendar_delete_event": handle_delete_event,
    "calendar_daily_agenda": handle_daily_agenda,
    "calendar_weekly_summary": handle_weekly_summary,
    "calendar_list_calendars": handle_list_calendars,
    "calendar_free_busy": handle_free_busy,
}


# ============================================================================
# SERVER FACTORY
# ============================================================================


def _register_handlers(server: Server) -> None:
    """Register MCP handlers on the server instance.
    
    This function registers the list_tools and call_tool handlers
    on the provided server instance.
    """
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available Calendar tools."""
        return CALENDAR_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls by dispatching to the appropriate handler."""
        handler = TOOL_HANDLERS.get(name)
        
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        try:
            return await handler(arguments)
        except Exception as e:
            logger.error(f"Error in tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]


def create_mcp_server() -> Server:
    """Factory function to create a fresh MCP server instance.
    
    Creates a new Server instance with all handlers registered.
    Use this function for SSE connections to ensure proper session isolation.
    Each connection gets its own server instance to avoid state conflicts.
    
    Returns:
        A configured Server instance ready to handle MCP requests.
    """
    server = Server("google-calendar-mcp")
    _register_handlers(server)
    logger.debug("Created new MCP server instance")
    return server


# Create a default server instance for stdio mode
server = create_mcp_server()


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the MCP server in stdio mode."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    logger.info("Starting Google Calendar MCP Server...")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)

    asyncio.run(run())


if __name__ == "__main__":
    main()
