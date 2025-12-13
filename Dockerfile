# syntax=docker/dockerfile:1

# Multi-stage build for Google Calendar MCP server
# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the package in editable mode with all dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create credentials directory
RUN mkdir -p /app/credentials

# Set Python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default environment variables
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8002
ENV LOG_LEVEL=INFO
ENV CREDENTIALS_PATH=/app/credentials/client_secrets.json
ENV TOKEN_PATH=/app/credentials/token.json
ENV CALENDARS_CONFIG_PATH=/app/config/calendars.yaml

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

# Default command - run combined server
CMD ["python", "-m", "mcp_google_calendar.combined_server"]
