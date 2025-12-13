"""Tests for configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_google_calendar.config import CalendarCategory, CalendarsConfig, Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        with patch.dict(os.environ, {}, clear=True):
            # Create settings with defaults
            settings = Settings(
                credentials_path="credentials/client_secrets.json",
                token_path="credentials/token.json",
            )
            assert settings.mcp_server_host == "0.0.0.0"
            assert settings.mcp_server_port == "8002"
            assert settings.log_level == "INFO"

    def test_settings_from_env(self):
        """Test settings loaded from environment."""
        env_vars = {
            "MCP_SERVER_HOST": "127.0.0.1",
            "MCP_SERVER_PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "CREDENTIALS_PATH": "/custom/creds.json",
            "TOKEN_PATH": "/custom/token.json",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.mcp_server_host == "127.0.0.1"
            assert settings.mcp_server_port == "9000"
            assert settings.log_level == "DEBUG"


class TestCalendarsConfig:
    """Test CalendarsConfig class."""

    def test_calendar_category(self):
        """Test CalendarCategory model."""
        category = CalendarCategory(
            name="Work",
            calendar_ids=["work@group.calendar.google.com"],
            description="Work calendar",
            color="#0000FF",
        )
        assert category.name == "Work"
        assert len(category.calendar_ids) == 1
        assert category.description == "Work calendar"
        assert category.color == "#0000FF"

    def test_calendars_config(self):
        """Test CalendarsConfig model."""
        config = CalendarsConfig(
            categories=[
                CalendarCategory(
                    name="Work",
                    calendar_ids=["work@group.calendar.google.com"],
                ),
                CalendarCategory(
                    name="Personal",
                    calendar_ids=["personal@gmail.com"],
                ),
            ]
        )
        assert len(config.categories) == 2
        assert config.categories[0].name == "Work"
        assert config.categories[1].name == "Personal"

    def test_get_calendars_by_category(self):
        """Test getting calendars by category name."""
        config = CalendarsConfig(
            categories=[
                CalendarCategory(
                    name="Work",
                    calendar_ids=["work1@group.calendar.google.com", "work2@group.calendar.google.com"],
                ),
            ]
        )
        work_category = next((c for c in config.categories if c.name == "Work"), None)
        assert work_category is not None
        assert len(work_category.calendar_ids) == 2
