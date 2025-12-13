"""Combined REST API and MCP SSE server.

This module runs both the REST API and MCP server on a single port,
allowing Home Assistant REST integration and Claude Desktop MCP access.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from .api import (
    CalendarResponse,
    DailySummaryResponse,
    EventResponse,
    HealthResponse,
    WeekSummaryResponse,
    find_free_time,
    get_client,
    get_daily_summary,
    get_today_events,
    get_upcoming_events,
    get_weekly_summary,
    list_calendars,
    search_events,
)
from .auth import CalendarAuth
from .calendar_client import CalendarClient
from .config import get_calendars_config, get_settings
from .server import server as mcp_server

logger = logging.getLogger(__name__)

# Create SSE transport for MCP
sse = SseServerTransport("/mcp/messages/")

# Global client for health check
_client: Optional[CalendarClient] = None


def ensure_client() -> Optional[CalendarClient]:
    """Ensure the calendar client is initialized."""
    global _client
    if _client is None:
        try:
            _client = get_client()
        except Exception as e:
            logger.warning(f"Could not initialize calendar client: {e}")
    return _client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Google Calendar MCP Combined Server")
    ensure_client()
    yield
    logger.info("Shutting down Google Calendar MCP Combined Server")


# Create the combined FastAPI app
app = FastAPI(
    title="Google Calendar MCP Combined Server",
    description="Combined REST API and MCP SSE server for Google Calendar",
    version="0.1.0",
    lifespan=lifespan,
)


# === Health Endpoint ===


@app.get("/health")
async def health_check():
    """Health check endpoint for both REST API and MCP."""
    try:
        client = ensure_client()
        if client:
            calendars_config = get_calendars_config()
            return {
                "status": "healthy",
                "authenticated": True,
                "calendars_loaded": len(calendars_config.categories) if calendars_config else 0,
                "mcp_enabled": True,
                "rest_enabled": True,
            }
        else:
            return {
                "status": "degraded",
                "authenticated": False,
                "calendars_loaded": 0,
                "mcp_enabled": True,
                "rest_enabled": True,
                "message": "Calendar client not initialized. Run auth first.",
            }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "authenticated": False,
            "error": str(e),
        }


# === REST API Endpoints ===

# Mount the REST API endpoints directly
app.get("/calendars", response_model=list[CalendarResponse])(list_calendars)
app.get("/events/today", response_model=list[EventResponse])(get_today_events)
app.get("/events/upcoming", response_model=list[EventResponse])(get_upcoming_events)
app.get("/events/search", response_model=list[EventResponse])(search_events)
app.get("/summary/daily", response_model=DailySummaryResponse)(get_daily_summary)
app.get("/summary/weekly", response_model=WeekSummaryResponse)(get_weekly_summary)
app.get("/free-time")(find_free_time)


# === MCP SSE Endpoints ===


async def handle_sse(request: Request) -> Response:
    """Handle SSE connections from MCP clients."""
    logger.info(f"New MCP SSE connection from {request.client}")

    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options(),
        )

    return Response()


async def handle_mcp_messages(request: Request) -> Response:
    """Handle MCP message posts."""
    return await sse.handle_post_message(request.scope, request.receive, request._send)


# Add MCP routes
app.add_route("/mcp/sse", handle_sse, methods=["GET"])
app.mount("/mcp/messages/", app=sse.handle_post_message)


# === Info endpoint ===


@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "Google Calendar MCP Server",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "calendars": "/calendars",
            "today": "/events/today",
            "upcoming": "/events/upcoming?days=7",
            "search": "/events/search?q=meeting",
            "daily_summary": "/summary/daily",
            "weekly_summary": "/summary/weekly",
            "free_time": "/free-time?duration_minutes=60&days=7",
            "mcp_sse": "/mcp/sse",
        },
        "documentation": "/docs",
    }


def main():
    """Run the combined server."""
    import uvicorn

    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    port = int(settings.mcp_server_port)
    host = settings.mcp_server_host

    logger.info(f"Starting Combined Server on http://{host}:{port}")
    logger.info(f"REST API docs: http://{host}:{port}/docs")
    logger.info(f"MCP SSE endpoint: http://{host}:{port}/mcp/sse")
    logger.info(f"Health check: http://{host}:{port}/health")

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
