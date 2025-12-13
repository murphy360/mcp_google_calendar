"""MCP Server implementation for Google Calendar."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
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

# Initialize server
server = Server("google-calendar-mcp")

# Global client instance
_calendar_client: CalendarClient | None = None


def get_calendar_client() -> CalendarClient:
    """Get or create Calendar client instance."""
    global _calendar_client
    if _calendar_client is None:
        settings = get_settings()
        calendars_config = get_calendars_config(settings)
        _calendar_client = CalendarClient(settings, calendars_config)
    return _calendar_client


# ============================================================================
# TOOLS
# ============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Calendar tools."""
    return [
        Tool(
            name="calendar_list_events",
            description="List upcoming calendar events. Can filter by date range and calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to look (default: 7)",
                        "default": 7,
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')",
                        "default": "primary",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="calendar_search",
            description="Search calendar events by text query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to search",
                        "default": 30,
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days back to search",
                        "default": 0,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="calendar_get_event",
            description="Get details of a specific calendar event by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')",
                        "default": "primary",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="calendar_create_event",
            description="Create a new calendar event",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Event title/summary",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g., '2024-12-15T14:00:00')",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (optional, defaults to start + 1 hour)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description",
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location",
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses",
                    },
                    "all_day": {
                        "type": "boolean",
                        "description": "Whether this is an all-day event",
                        "default": False,
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')",
                        "default": "primary",
                    },
                },
                "required": ["summary", "start_time"],
            },
        ),
        Tool(
            name="calendar_update_event",
            description="Update an existing calendar event",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to update",
                    },
                    "summary": {
                        "type": "string",
                        "description": "New event title",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "New start time in ISO format",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "New end time in ISO format",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description",
                    },
                    "location": {
                        "type": "string",
                        "description": "New location",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID",
                        "default": "primary",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="calendar_delete_event",
            description="Delete a calendar event",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to delete",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID",
                        "default": "primary",
                    },
                    "notify_attendees": {
                        "type": "boolean",
                        "description": "Whether to notify attendees",
                        "default": True,
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="calendar_daily_agenda",
            description="Get today's agenda with all events from one or more calendars",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (default: today)",
                    },
                    "calendar_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of calendar IDs to include (default: all calendars). Use 'primary' for main calendar or specific calendar IDs.",
                    },
                },
            },
        ),
        Tool(
            name="calendar_weekly_summary",
            description="Get a summary of the week's events from one or more calendars",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Week start date in YYYY-MM-DD format (default: current week)",
                    },
                    "calendar_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of calendar IDs to include (default: all calendars). Use 'primary' for main calendar or specific calendar IDs.",
                    },
                },
            },
        ),
        Tool(
            name="calendar_list_calendars",
            description="List all available calendars",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="calendar_free_busy",
            description="Check free/busy status for a time range",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format",
                    },
                    "calendar_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Calendar IDs to check (default: ['primary'])",
                    },
                },
                "required": ["start_time", "end_time"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    client = get_calendar_client()
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    try:
        if name == "calendar_list_events":
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
                start = event.start_datetime
                if event.is_all_day:
                    time_str = "All day"
                elif start:
                    time_str = start.strftime("%a %b %d, %I:%M %p")
                else:
                    time_str = "Unknown time"

                lines.append(f"• {event.summary}")
                lines.append(f"  📆 {time_str}")
                if event.location:
                    lines.append(f"  📍 {event.location}")
                if event.meeting_link:
                    lines.append(f"  🔗 {event.meeting_link}")
                lines.append(f"  ID: {event.id}")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "calendar_search":
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
                start = event.start_datetime
                time_str = start.strftime("%a %b %d, %I:%M %p") if start else "Unknown"
                lines.append(f"• {event.summary}")
                lines.append(f"  📆 {time_str}")
                lines.append(f"  ID: {event.id}")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "calendar_get_event":
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
                lines.append(f"Start: {start.strftime('%a %b %d, %Y %I:%M %p')}")
                lines.append(f"End: {end.strftime('%a %b %d, %Y %I:%M %p')}")
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

        elif name == "calendar_create_event":
            start_time = datetime.fromisoformat(arguments["start_time"])
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=tz)

            end_time = None
            if arguments.get("end_time"):
                end_time = datetime.fromisoformat(arguments["end_time"])
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=tz)

            request = EventCreateRequest(
                summary=arguments["summary"],
                start_time=start_time,
                end_time=end_time,
                description=arguments.get("description"),
                location=arguments.get("location"),
                attendees=arguments.get("attendees", []),
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

        elif name == "calendar_update_event":
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

        elif name == "calendar_delete_event":
            event_id = arguments["event_id"]
            calendar_id = arguments.get("calendar_id", "primary")
            notify = arguments.get("notify_attendees", True)

            await client.delete_event(event_id, calendar_id, notify)

            return [TextContent(type="text", text=f"✅ Event deleted successfully (ID: {event_id})")]

        elif name == "calendar_daily_agenda":
            date = None
            if arguments.get("date"):
                date = datetime.strptime(arguments["date"], "%Y-%m-%d").replace(tzinfo=tz)

            # Get calendar_ids - default to all calendars if not specified
            calendar_ids = arguments.get("calendar_ids")
            if not calendar_ids:
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
                    start = event.start_datetime
                    time_str = start.strftime("%I:%M %p") if start else ""
                    lines.append(f"  • {time_str} - {event.summary}")
                    if event.location:
                        lines.append(f"    📍 {event.location}")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "calendar_weekly_summary":
            start_date = None
            if arguments.get("start_date"):
                start_date = datetime.strptime(arguments["start_date"], "%Y-%m-%d").replace(tzinfo=tz)

            # Get calendar_ids - default to all calendars if not specified
            calendar_ids = arguments.get("calendar_ids")
            if not calendar_ids:
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
                for event in events[:3]:
                    start = event.start_datetime
                    time_str = start.strftime("%I:%M %p") if start else "All day"
                    lines.append(f"  • {time_str} - {event.summary}")
                if len(events) > 3:
                    lines.append(f"  ... and {len(events) - 3} more")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "calendar_list_calendars":
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

        elif name == "calendar_free_busy":
            start_time = datetime.fromisoformat(arguments["start_time"])
            end_time = datetime.fromisoformat(arguments["end_time"])

            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=tz)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=tz)

            request = FreeBusyRequest(
                time_min=start_time,
                time_max=end_time,
                calendar_ids=arguments.get("calendar_ids", ["primary"]),
            )

            results = await client.get_free_busy(request)

            lines = [f"📊 Free/Busy Status ({start_time.strftime('%b %d %I:%M %p')} - {end_time.strftime('%b %d %I:%M %p')})\n"]

            for result in results:
                lines.append(f"Calendar: {result.calendar_id}")
                if not result.busy:
                    lines.append("  ✅ Free during this time")
                else:
                    lines.append(f"  ❌ Busy ({len(result.busy)} conflicts):")
                    for slot in result.busy[:5]:
                        lines.append(
                            f"    • {slot.start.strftime('%I:%M %p')} - {slot.end.strftime('%I:%M %p')}"
                        )
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the MCP server."""
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
