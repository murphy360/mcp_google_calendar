"""Configuration settings for MCP Google Calendar Server."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google OAuth
    google_client_id: str = Field(default="", description="Google OAuth Client ID")
    google_client_secret: str = Field(default="", description="Google OAuth Client Secret")

    # Paths
    credentials_dir: Path = Field(
        default=Path("credentials"), description="Directory for OAuth credentials"
    )
    config_dir: Path = Field(default=Path("config"), description="Directory for config files")

    # Server
    mcp_server_host: str = Field(default="0.0.0.0", description="Server host")
    mcp_server_port: int = Field(default=8000, description="Server port")
    log_level: str = Field(default="INFO", description="Logging level")

    # Calendar defaults
    default_calendar_id: str = Field(default="primary", description="Default calendar ID")
    timezone: str = Field(default="America/New_York", description="Default timezone")

    # Home Assistant
    ha_webhook_url: Optional[str] = Field(default=None, description="Home Assistant webhook URL")
    ha_long_lived_token: Optional[str] = Field(
        default=None, description="Home Assistant long-lived token"
    )

    # OAuth scopes for Calendar
    oauth_scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        description="OAuth scopes for Calendar API",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def client_secrets_file(self) -> Path:
        """Path to client secrets file."""
        return self.credentials_dir / "client_secrets.json"

    @property
    def token_file(self) -> Path:
        """Path to OAuth token file."""
        return self.credentials_dir / "token.json"

    @property
    def calendars_config_file(self) -> Path:
        """Path to calendars configuration file."""
        return self.config_dir / "calendars.yaml"


class CalendarCategory:
    """Calendar category configuration."""

    def __init__(
        self,
        key: str,
        name: str,
        description: str = "",
        calendar_ids: list[str] | None = None,
        keywords: list[str] | None = None,
        color: str = "#4285F4",
        priority: int = 10,
    ):
        self.key = key
        self.name = name
        self.description = description
        self.calendar_ids = calendar_ids or []
        self.keywords = keywords or []
        self.color = color
        self.priority = priority

    def matches_calendar(self, calendar_id: str) -> bool:
        """Check if a calendar ID matches this category."""
        return calendar_id in self.calendar_ids

    def matches_event(self, event_summary: str, event_description: str = "") -> bool:
        """Check if an event matches this category by keywords."""
        text = f"{event_summary} {event_description}".lower()
        return any(keyword.lower() in text for keyword in self.keywords)


class CalendarsConfig:
    """Calendars configuration container."""

    def __init__(self, categories: list[CalendarCategory], defaults: dict):
        self.categories = sorted(categories, key=lambda c: c.priority)
        self.defaults = defaults

    def categorize_event(
        self, calendar_id: str, event_summary: str, event_description: str = ""
    ) -> CalendarCategory | None:
        """Categorize an event based on calendar and content."""
        # First check by calendar ID
        for category in self.categories:
            if category.matches_calendar(calendar_id):
                return category

        # Then check by keywords
        for category in self.categories:
            if category.matches_event(event_summary, event_description):
                return category

        return None

    def get_category(self, key: str) -> CalendarCategory | None:
        """Get category by key."""
        for category in self.categories:
            if category.key == key:
                return category
        return None


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_calendars_config(settings: Settings | None = None) -> CalendarsConfig:
    """Load calendars configuration from YAML file."""
    settings = settings or get_settings()

    if not settings.calendars_config_file.exists():
        # Return default configuration
        return CalendarsConfig(
            categories=[
                CalendarCategory(
                    key="primary",
                    name="Primary",
                    description="Primary calendar",
                    calendar_ids=["primary"],
                    priority=1,
                )
            ],
            defaults={
                "time_zone": settings.timezone,
                "default_duration_minutes": 60,
                "reminder_minutes": [10, 30],
            },
        )

    with open(settings.calendars_config_file) as f:
        config = yaml.safe_load(f)

    categories = []
    for key, cat_config in config.get("calendars", {}).items():
        categories.append(
            CalendarCategory(
                key=key,
                name=cat_config.get("name", key.title()),
                description=cat_config.get("description", ""),
                calendar_ids=cat_config.get("calendar_ids", []),
                keywords=cat_config.get("keywords", []),
                color=cat_config.get("color", "#4285F4"),
                priority=cat_config.get("priority", 10),
            )
        )

    defaults = config.get("defaults", {})

    return CalendarsConfig(categories=categories, defaults=defaults)
