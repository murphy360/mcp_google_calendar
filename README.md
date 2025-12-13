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
docker compose --profile setup run --rm calendar-mcp-auth
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
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["-y", "mcp-remote", "http://YOUR_SERVER_IP:8003/mcp/sse", "--allow-http"]
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `calendar_list_events` | List upcoming events with optional filters |
| `calendar_search` | Search events by text query |
| `calendar_get_event` | Get details of a specific event |
| `calendar_create_event` | Create a new calendar event |
| `calendar_update_event` | Update an existing event |
| `calendar_delete_event` | Delete an event |
| `calendar_daily_agenda` | Get today's agenda summary |
| `calendar_weekly_summary` | Get week overview |
| `calendar_list_calendars` | List all available calendars |
| `calendar_free_busy` | Check availability for a time range |

## REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/events/today` | Today's events |
| `GET /api/events/upcoming` | Upcoming events |
| `GET /api/agenda/daily` | Daily agenda text |
| `GET /api/calendars` | List calendars |

## Home Assistant Integration

### REST Sensor Example

```yaml
sensor:
  - platform: rest
    name: "Next Calendar Event"
    resource: http://YOUR_SERVER_IP:8003/api/events/upcoming?max_results=1
    value_template: "{{ value_json.events[0].summary if value_json.events else 'No events' }}"
    scan_interval: 300

  - platform: rest
    name: "Today's Events Count"
    resource: http://YOUR_SERVER_IP:8003/api/events/today
    value_template: "{{ value_json.count }}"
    scan_interval: 300
```

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
