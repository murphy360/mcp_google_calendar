"""REST API for Google Calendar MCP server.

This provides HTTP endpoints for Home Assistant and other integrations.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .auth import CalendarAuth
from .calendar_client import CalendarClient
from .config import get_calendars_config, get_settings

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Google Calendar MCP API",
    description="REST API for Google Calendar integration",
    version="0.1.0",
)

# Global client instance
_client: Optional[CalendarClient] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    authenticated: bool
    calendars_loaded: int


class CalendarResponse(BaseModel):
    """Calendar info response."""

    id: str
    summary: str
    description: Optional[str] = None
    primary: bool = False
    access_role: Optional[str] = None


class EventResponse(BaseModel):
    """Event response."""

    id: str
    summary: str
    start: str
    end: str
    location: Optional[str] = None
    description: Optional[str] = None
    calendar_id: Optional[str] = None
    html_link: Optional[str] = None
    status: str = "confirmed"
    all_day: bool = False


class DailySummaryResponse(BaseModel):
    """Daily summary response."""

    date: str
    total_events: int
    events: list[dict]
    categories: dict[str, list[dict]]


class WeekSummaryResponse(BaseModel):
    """Week summary response."""

    start_date: str
    end_date: str
    total_events: int
    days: list[dict]


def get_client() -> CalendarClient:
    """Get or create the calendar client."""
    global _client
    if _client is None:
        settings = get_settings()
        calendars_config = get_calendars_config()
        _client = CalendarClient(settings=settings, calendars_config=calendars_config)
    return _client


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    try:
        client = get_client()
        calendars = await client.list_calendars()
        calendars_config = get_calendars_config()
        return HealthResponse(
            status="healthy",
            authenticated=True,
            calendars_loaded=len(calendars_config.categories) if calendars_config else 0,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            authenticated=False,
            calendars_loaded=0,
        )


@app.get("/calendars", response_model=list[CalendarResponse])
async def list_calendars():
    """List all accessible calendars."""
    try:
        client = get_client()
        calendars = await client.list_calendars()
        return [
            CalendarResponse(
                id=cal.id,
                summary=cal.summary,
                description=cal.description,
                primary=cal.primary,
                access_role=cal.access_role,
            )
            for cal in calendars
        ]
    except Exception as e:
        logger.error(f"Failed to list calendars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/today", response_model=list[EventResponse])
async def get_today_events(
    calendar_id: Optional[str] = Query(None, description="Filter by calendar ID"),
):
    """Get today's events."""
    try:
        client = get_client()
        today = date.today()
        cal_id = calendar_id or "primary"
        events = await client.list_events(
            calendar_id=cal_id,
            time_min=datetime.combine(today, datetime.min.time()),
            time_max=datetime.combine(today, datetime.max.time()),
        )
        return [
            EventResponse(
                id=event.id,
                summary=event.summary,
                start=event.start.date_time.isoformat()
                if event.start.date_time
                else event.start.date or "",
                end=event.end.date_time.isoformat()
                if event.end.date_time
                else event.end.date or "",
                location=event.location,
                description=event.description,
                calendar_id=event.calendar_id,
                html_link=event.html_link,
                status=event.status,
                all_day=event.start.date is not None,
            )
            for event in events
        ]
    except Exception as e:
        logger.error(f"Failed to get today's events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/upcoming", response_model=list[EventResponse])
async def get_upcoming_events(
    days: int = Query(7, ge=1, le=30, description="Number of days to look ahead"),
    calendar_id: Optional[str] = Query(None, description="Filter by calendar ID"),
    max_results: int = Query(50, ge=1, le=250, description="Maximum number of results"),
):
    """Get upcoming events for the next N days."""
    try:
        client = get_client()
        now = datetime.now()
        end = now + timedelta(days=days)
        cal_id = calendar_id or "primary"
        events = await client.list_events(
            calendar_id=cal_id,
            time_min=now,
            time_max=end,
            max_results=max_results,
        )
        return [
            EventResponse(
                id=event.id,
                summary=event.summary,
                start=event.start.date_time.isoformat()
                if event.start.date_time
                else event.start.date or "",
                end=event.end.date_time.isoformat()
                if event.end.date_time
                else event.end.date or "",
                location=event.location,
                description=event.description,
                calendar_id=event.calendar_id,
                html_link=event.html_link,
                status=event.status,
                all_day=event.start.date is not None,
            )
            for event in events
        ]
    except Exception as e:
        logger.error(f"Failed to get upcoming events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/search", response_model=list[EventResponse])
async def search_events(
    q: str = Query(..., description="Search query"),
    days: int = Query(30, ge=1, le=365, description="Number of days to search"),
    calendar_id: Optional[str] = Query(None, description="Filter by calendar ID"),
    max_results: int = Query(50, ge=1, le=250, description="Maximum number of results"),
):
    """Search events by query string."""
    try:
        client = get_client()
        now = datetime.now()
        end = now + timedelta(days=days)
        cal_id = calendar_id or "primary"
        events = await client.search_events(
            query=q,
            calendar_id=cal_id,
            time_min=now,
            time_max=end,
            max_results=max_results,
        )
        return [
            EventResponse(
                id=event.id,
                summary=event.summary,
                start=event.start.date_time.isoformat()
                if event.start.date_time
                else event.start.date or "",
                end=event.end.date_time.isoformat()
                if event.end.date_time
                else event.end.date or "",
                location=event.location,
                description=event.description,
                calendar_id=event.calendar_id,
                html_link=event.html_link,
                status=event.status,
                all_day=event.start.date is not None,
            )
            for event in events
        ]
    except Exception as e:
        logger.error(f"Failed to search events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary/daily", response_model=DailySummaryResponse)
async def get_daily_summary(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    calendar_ids: Optional[str] = Query(None, description="Comma-separated list of calendar IDs (default: all calendars)"),
):
    """Get daily calendar summary."""
    try:
        client = get_client()
        if target_date:
            summary_date = datetime.fromisoformat(target_date)
        else:
            summary_date = datetime.now()

        # Parse calendar_ids - default to all calendars
        cal_ids = None
        if calendar_ids:
            cal_ids = [cid.strip() for cid in calendar_ids.split(",")]
        else:
            # Get all available calendars
            all_calendars = await client.list_calendars()
            cal_ids = [cal.id for cal in all_calendars]

        agenda = await client.get_daily_agenda(summary_date, calendar_ids=cal_ids)
        return DailySummaryResponse(
            date=agenda.date,
            total_events=agenda.event_count,
            events=[
                {
                    "id": e.id,
                    "summary": e.summary,
                    "start": e.start.date_time.isoformat()
                    if e.start.date_time
                    else e.start.date,
                    "end": e.end.date_time.isoformat() if e.end.date_time else e.end.date,
                    "location": e.location,
                    "calendar_id": e.calendar_id,
                    "all_day": e.start.date is not None,
                }
                for e in agenda.events
            ],
            categories={
                cat: [
                    {
                        "id": e.id,
                        "summary": e.summary,
                        "start": e.start.date_time.isoformat()
                        if e.start.date_time
                        else e.start.date,
                        "end": e.end.date_time.isoformat()
                        if e.end.date_time
                        else e.end.date,
                        "location": e.location,
                        "calendar_id": e.calendar_id,
                    }
                    for e in cat_events
                ]
                for cat, cat_events in agenda.categories.items()
            },
        )
    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary/weekly", response_model=WeekSummaryResponse)
async def get_weekly_summary(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    calendar_ids: Optional[str] = Query(None, description="Comma-separated list of calendar IDs (default: all calendars)"),
):
    """Get weekly calendar summary."""
    try:
        client = get_client()
        if start_date:
            summary_start = datetime.fromisoformat(start_date)
        else:
            # Start from Monday of current week
            today = datetime.now()
            summary_start = today - timedelta(days=today.weekday())

        # Parse calendar_ids - default to all calendars
        cal_ids = None
        if calendar_ids:
            cal_ids = [cid.strip() for cid in calendar_ids.split(",")]
        else:
            # Get all available calendars
            all_calendars = await client.list_calendars()
            cal_ids = [cal.id for cal in all_calendars]

        summary = await client.get_weekly_summary(summary_start, calendar_ids=cal_ids)
        return WeekSummaryResponse(
            start_date=summary.week_start,
            end_date=summary.week_end,
            total_events=summary.total_events,
            days=[
                {
                    "date": day_date,
                    "total_events": len(day_events),
                    "events": [
                        {
                            "id": e.id,
                            "summary": e.summary,
                            "start": e.start.date_time.isoformat()
                            if e.start.date_time
                            else e.start.date,
                            "end": e.end.date_time.isoformat()
                            if e.end.date_time
                            else e.end.date,
                            "location": e.location,
                            "calendar_id": e.calendar_id,
                        }
                        for e in day_events
                    ],
                }
                for day_date, day_events in summary.events_by_day.items()
            ],
        )
    except Exception as e:
        logger.error(f"Failed to get weekly summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/free-time")
async def find_free_time(
    duration_minutes: int = Query(60, ge=15, le=480, description="Required duration in minutes"),
    days: int = Query(7, ge=1, le=14, description="Days to search"),
    start_hour: int = Query(9, ge=0, le=23, description="Working hours start"),
    end_hour: int = Query(17, ge=1, le=24, description="Working hours end"),
):
    """Find free time slots."""
    try:
        client = get_client()
        now = datetime.now()
        end = now + timedelta(days=days)
        slots = await client.find_free_slots(
            time_min=now,
            time_max=end,
            duration_minutes=duration_minutes,
            working_hours_start=start_hour,
            working_hours_end=end_hour,
        )
        return [
            {
                "start": slot["start"].isoformat(),
                "end": slot["end"].isoformat(),
                "duration_minutes": (slot["end"] - slot["start"]).seconds // 60,
            }
            for slot in slots[:10]  # Return top 10 slots
        ]
    except Exception as e:
        logger.error(f"Failed to find free time: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the REST API server."""
    import uvicorn

    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info(f"Starting Calendar REST API on http://{settings.mcp_server_host}:{settings.mcp_server_port}")
    uvicorn.run(
        app,
        host=settings.mcp_server_host,
        port=int(settings.mcp_server_port),
    )


if __name__ == "__main__":
    main()
