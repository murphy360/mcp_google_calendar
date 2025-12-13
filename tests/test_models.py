"""Tests for models module."""

from datetime import date, datetime, timezone

import pytest

from mcp_google_calendar.models import (
    Attendee,
    CalendarInfo,
    DailySummary,
    Event,
    EventDateTime,
    EventsResponse,
    WeekSummary,
)


class TestEventDateTime:
    """Test EventDateTime model."""

    def test_datetime_event(self):
        """Test event with specific datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        event_dt = EventDateTime(datetime=dt, timezone="UTC")
        assert event_dt.datetime == dt
        assert event_dt.timezone == "UTC"
        assert event_dt.date is None

    def test_all_day_event(self):
        """Test all-day event with date only."""
        d = "2024-01-15"
        event_dt = EventDateTime(date=d)
        assert event_dt.date == d
        assert event_dt.datetime is None


class TestAttendee:
    """Test Attendee model."""

    def test_attendee_creation(self):
        """Test creating an attendee."""
        attendee = Attendee(
            email="test@example.com",
            display_name="Test User",
            response_status="accepted",
            organizer=False,
            self_=True,
        )
        assert attendee.email == "test@example.com"
        assert attendee.display_name == "Test User"
        assert attendee.response_status == "accepted"
        assert attendee.organizer is False
        assert attendee.self_ is True

    def test_attendee_minimal(self):
        """Test attendee with minimal fields."""
        attendee = Attendee(email="test@example.com")
        assert attendee.email == "test@example.com"
        assert attendee.display_name is None
        assert attendee.response_status is None


class TestEvent:
    """Test Event model."""

    def test_event_creation(self):
        """Test creating an event."""
        start = EventDateTime(datetime=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        end = EventDateTime(datetime=datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc))
        
        event = Event(
            id="event123",
            summary="Test Meeting",
            start=start,
            end=end,
            calendar_id="primary",
            status="confirmed",
        )
        assert event.id == "event123"
        assert event.summary == "Test Meeting"
        assert event.start == start
        assert event.end == end
        assert event.status == "confirmed"

    def test_event_with_attendees(self):
        """Test event with attendees."""
        start = EventDateTime(datetime=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        end = EventDateTime(datetime=datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc))
        
        event = Event(
            id="event123",
            summary="Team Meeting",
            start=start,
            end=end,
            calendar_id="primary",
            attendees=[
                Attendee(email="user1@example.com", response_status="accepted"),
                Attendee(email="user2@example.com", response_status="tentative"),
            ],
        )
        assert len(event.attendees) == 2
        assert event.attendees[0].email == "user1@example.com"


class TestCalendarInfo:
    """Test CalendarInfo model."""

    def test_calendar_info(self):
        """Test calendar info creation."""
        cal = CalendarInfo(
            id="primary",
            summary="My Calendar",
            description="Primary calendar",
            primary=True,
            access_role="owner",
        )
        assert cal.id == "primary"
        assert cal.summary == "My Calendar"
        assert cal.primary is True
        assert cal.access_role == "owner"


class TestEventsResponse:
    """Test EventsResponse model."""

    def test_events_response(self):
        """Test events response creation."""
        start = EventDateTime(datetime=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        end = EventDateTime(datetime=datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc))
        
        event = Event(
            id="event123",
            summary="Test",
            start=start,
            end=end,
            calendar_id="primary",
        )
        
        response = EventsResponse(
            events=[event],
            next_page_token="token123",
        )
        assert len(response.events) == 1
        assert response.next_page_token == "token123"


class TestDailySummary:
    """Test DailySummary model."""

    def test_daily_summary(self):
        """Test daily summary creation."""
        start = EventDateTime(datetime=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc))
        end = EventDateTime(datetime=datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc))
        
        event = Event(
            id="event123",
            summary="Test",
            start=start,
            end=end,
            calendar_id="primary",
        )
        
        summary = DailySummary(
            date=date(2024, 1, 15),
            events=[event],
            total_events=1,
            by_category={"Work": [event]},
        )
        assert summary.date == date(2024, 1, 15)
        assert summary.total_events == 1
        assert len(summary.events) == 1
        assert "Work" in summary.by_category


class TestWeekSummary:
    """Test WeekSummary model."""

    def test_week_summary(self):
        """Test week summary creation."""
        day1 = DailySummary(
            date=date(2024, 1, 15),
            events=[],
            total_events=0,
            by_category={},
        )
        day2 = DailySummary(
            date=date(2024, 1, 16),
            events=[],
            total_events=2,
            by_category={},
        )
        
        week = WeekSummary(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 21),
            days=[day1, day2],
            total_events=2,
        )
        assert week.start_date == date(2024, 1, 15)
        assert week.end_date == date(2024, 1, 21)
        assert week.total_events == 2
        assert len(week.days) == 2
