# Google Calendar MCP Server

A Model Context Protocol (MCP) server for Google Calendar integration, designed for personal calendar management with Home Assistant support.

## Features

- **MCP Tools**: Search events, list upcoming events, create/update/delete events
- **Daily Agenda**: Get formatted daily agenda summaries
- **Calendar Categories**: Organize calendars by type (work, personal, family, etc.)
- **REST API**: Endpoints for Home Assistant integration
- **SSE Transport**: Connect from Claude Desktop via mcp-remote
- **Docker Support**: Easy deployment with Docker Compose

## Quick Start

### 1. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Google Calendar API**
4. Create OAuth 2.0 credentials (Desktop App type)
5. Download the credentials

### 2. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
# GOOGLE_CLIENT_ID=your-client-id
# GOOGLE_CLIENT_SECRET=your-client-secret
```

### 3. Initial OAuth Setup

```bash
# Run OAuth setup (opens browser for consent)
docker compose --profile setup run --rm calendar-auth
```

### 4. Start the Server

```bash
docker compose up -d
```

### 5. Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "calendar": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://YOUR_SERVER_IP:8002/mcp/sse", "--allow-http"]
    }
  }
}
```

### Home Assistant MCP Integration

The server exposes SSE endpoints for MCP connections:
- `/mcp/sse` - Primary MCP SSE endpoint
- `/sse` - Alias endpoint for Home Assistant compatibility

Each connection gets a fresh server instance for proper session isolation.

## MCP Tools

| Tool | Description |
|------|-------------|
| `calendar_get_current_time` | Get current date/time with reference dates for queries |
| `calendar_list_events` | List upcoming events with optional filters |
| `calendar_search` | Search events by text query |
| `calendar_get_event` | Get details of a specific event |
| `calendar_create_event` | Create a new calendar event |
| `calendar_update_event` | Update an existing event |
| `calendar_delete_event` | Delete an event |
| `calendar_daily_agenda` | Get agenda for a specific day |
| `calendar_weekly_summary` | Get 7-day overview |
| `calendar_list_calendars` | List all available calendars |
| `calendar_free_busy` | Check availability for a time range |

### Tool Schema Notes

All tools use Gemini-compatible schemas with explicit types:
- Array parameters use comma-separated strings (e.g., `attendees: "user1@example.com,user2@example.com"`)
- Calendar IDs use comma-separated strings (e.g., `calendar_ids: "primary,work@group.calendar.google.com"`)
- Dates use ISO 8601 format (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`)

## REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with auth status |
| `GET /calendars` | List all calendars |
| `GET /events/today` | Today's events |
| `GET /events/upcoming` | Upcoming events |
| `GET /events/search?q=query` | Search events |
| `GET /summary/daily` | Daily summary |
| `GET /summary/weekly` | Weekly summary |
| `GET /free-time` | Find free time slots |

## Home Assistant Integration

### REST Sensor Example

```yaml
sensor:
  - platform: rest
    name: "Next Calendar Event"
    resource: http://YOUR_SERVER_IP:8002/events/upcoming?days=1
    value_template: "{{ value_json[0].summary if value_json else 'No events' }}"
    scan_interval: 300

  - platform: rest
    name: "Today's Events Count"
    resource: http://YOUR_SERVER_IP:8002/events/today
    value_template: "{{ value_json | length }}"
    scan_interval: 300
```

### MCP Integration

Home Assistant can connect via the MCP SSE endpoints:
- `http://YOUR_SERVER_IP:8002/mcp/sse`
- `http://YOUR_SERVER_IP:8002/sse` (alias)

## Project Structure

```
mcp_google_calendar/
├── src/mcp_google_calendar/
│   ├── __init__.py
│   ├── auth.py              # OAuth2 authentication
│   ├── calendar_client.py   # Google Calendar API wrapper
│   ├── config.py            # Settings and configuration
│   ├── models.py            # Pydantic models
│   ├── server.py            # MCP stdio server
│   ├── sse_server.py        # MCP SSE server
│   ├── combined_server.py   # REST + SSE combined server
│   └── api.py               # REST API for Home Assistant
├── config/
│   └── calendars.yaml       # Calendar categorization
├── credentials/
│   ├── client_secrets.json  # OAuth credentials
│   └── token.json           # Stored tokens
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## License

MIT
