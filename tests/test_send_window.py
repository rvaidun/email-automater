"""Tests for shared send-window helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from utils import send_window

EASTERN_TZ = ZoneInfo("America/New_York")


def test_parse_allowed_weekdays_filters_invalid_values():
    """Only weekday integers from 0-6 should survive parsing."""
    allowed = send_window.parse_allowed_weekdays("0, 2, 9, -1, foo, 6")

    assert allowed == {0, 2, 6}


def test_parse_allowed_weekdays_falls_back_to_default_on_empty():
    """Empty config should use the helper defaults."""
    allowed = send_window.parse_allowed_weekdays("")

    assert allowed == set(send_window.DEFAULT_WEEKDAYS)


def test_within_send_window_respects_boundaries():
    """Window checks should be inclusive at start and exclusive at end."""
    allowed = {0, 1, 2, 3, 4, 6}
    inside_start = datetime(2026, 4, 12, 9, 0, tzinfo=EASTERN_TZ)
    before_start = datetime(2026, 4, 12, 8, 59, tzinfo=EASTERN_TZ)
    at_end = datetime(2026, 4, 12, 16, 30, tzinfo=EASTERN_TZ)

    assert (
        send_window.within_send_window(
            inside_start,
            timezone="America/New_York",
            allowed_weekdays=allowed,
        )
        is True
    )
    assert (
        send_window.within_send_window(
            before_start,
            timezone="America/New_York",
            allowed_weekdays=allowed,
        )
        is False
    )
    assert (
        send_window.within_send_window(
            at_end,
            timezone="America/New_York",
            allowed_weekdays=allowed,
        )
        is False
    )


def test_env_timezone_prefers_first_non_empty_env(monkeypatch):
    """Timezone resolution should honor env-name precedence."""
    monkeypatch.setenv("PRIMARY_TZ", "")
    monkeypatch.setenv("SECONDARY_TZ", "America/Chicago")

    value = send_window.env_timezone("PRIMARY_TZ", "SECONDARY_TZ", default="UTC")

    assert value == "America/Chicago"


def test_env_spacing_minutes_clamps_to_one(monkeypatch):
    """Spacing config should never go below one minute."""
    monkeypatch.setenv("TEST_SPACING", "0")

    assert send_window.env_spacing_minutes("TEST_SPACING", default=15) == 1


def test_load_schedule_windows_reads_csv_rows(tmp_path):
    """The editable scheduler CSV should load valid day/time rows."""
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n0,09:00,16:30\n6,09:00,16:30\n")

    windows = send_window.load_schedule_windows(schedule_path)

    assert len(windows) == 2
    assert windows[1].weekday == 6
    assert windows[1].start_hour == 9
    assert windows[1].end_minute == 30


def test_within_send_window_prefers_schedule_csv_when_present(tmp_path):
    """A schedule CSV should control the active send window when provided."""
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n6,14:30,16:30\n")
    inside = datetime(2026, 4, 12, 15, 0, tzinfo=EASTERN_TZ)
    outside = datetime(2026, 4, 12, 13, 0, tzinfo=EASTERN_TZ)

    assert (
        send_window.within_send_window(
            inside,
            timezone="America/New_York",
            allowed_weekdays={0, 1, 2, 3, 4},
            schedule_csv_path=schedule_path,
        )
        is True
    )
    assert (
        send_window.within_send_window(
            outside,
            timezone="America/New_York",
            allowed_weekdays={0, 1, 2, 3, 4},
            schedule_csv_path=schedule_path,
        )
        is False
    )
