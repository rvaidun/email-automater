"""Contains functions to help with pacing emails."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from utils.send_window import (
    DEFAULT_WEEKDAYS,
    day_window_ranges,
    normalize_allowed_weekdays,
)


def _resolved_allowed_weekdays(
    allowed_weekdays: set[int] | frozenset[int] | None,
) -> set[int]:
    return normalize_allowed_weekdays(allowed_weekdays, default=DEFAULT_WEEKDAYS)


def _window_bounds(
    now: datetime.datetime,
    *,
    timezone: str,
    allowed_weekdays: set[int] | frozenset[int] | None,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    minimum_delay_minutes: int,
    schedule_csv_path: str | None,
) -> tuple[datetime.datetime, list[tuple[datetime.datetime, datetime.datetime]]]:
    localized = now.astimezone(ZoneInfo(timezone))
    allowed_days = _resolved_allowed_weekdays(allowed_weekdays)
    earliest = localized + datetime.timedelta(minutes=minimum_delay_minutes)
    return earliest, day_window_ranges(
        now,
        timezone=timezone,
        allowed_weekdays=allowed_days,
        start_hour=start_hour,
        start_minute=start_minute,
        end_hour=end_hour,
        end_minute=end_minute,
        schedule_csv_path=schedule_csv_path,
    )


def paced_send_times(
    count: int,
    *,
    now: datetime.datetime,
    timezone: str,
    allowed_weekdays: set[int] | frozenset[int] | None = None,
    start_hour: int = 9,
    start_minute: int = 0,
    end_hour: int = 16,
    end_minute: int = 30,
    minimum_delay_minutes: int = 5,
    minimum_spacing_minutes: int = 15,
    schedule_csv_path: str | None = None,
) -> list[datetime.datetime]:
    """Return conservative same-day send slots with a fixed minimum gap."""
    if count <= 0:
        return []

    earliest, window_ranges = _window_bounds(
        now,
        timezone=timezone,
        allowed_weekdays=allowed_weekdays,
        start_hour=start_hour,
        start_minute=start_minute,
        end_hour=end_hour,
        end_minute=end_minute,
        minimum_delay_minutes=minimum_delay_minutes,
        schedule_csv_path=schedule_csv_path,
    )
    if not window_ranges:
        return []

    spacing = datetime.timedelta(minutes=max(minimum_spacing_minutes, 1))
    send_times: list[datetime.datetime] = []
    candidate = earliest
    for window_start, window_end in window_ranges:
        candidate = max(candidate, window_start)
        while len(send_times) < count and candidate <= window_end:
            send_times.append(candidate)
            candidate += spacing
        if len(send_times) >= count:
            break
    return send_times
