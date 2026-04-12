"""Shared helpers for send-window configuration."""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Iterable

LAST_WEEKDAY = 6
DEFAULT_WEEKDAYS = frozenset({0, 1, 2, 3, 4})
TIME_PART_COUNT = 2
MAX_HOUR = 23
MAX_MINUTE = 59


@dataclass(frozen=True, slots=True)
class ScheduleWindow:
    """One editable local send window from the scheduler CSV."""

    weekday: int
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int


def _parse_time(raw: str) -> tuple[int, int] | None:
    """Parse a HH:MM time value from the scheduler CSV."""
    parts = raw.strip().split(":", maxsplit=1)
    if len(parts) != TIME_PART_COUNT:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= MAX_HOUR and 0 <= minute <= MAX_MINUTE):
        return None
    return hour, minute


def load_schedule_windows(path_value: str | Path | None) -> list[ScheduleWindow]:
    """Load editable send windows from a scheduler CSV if one exists."""
    if not path_value:
        return []
    path = Path(path_value).expanduser()
    if not path.exists():
        return []

    windows: list[ScheduleWindow] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                weekday = int((row.get("DAY") or "").strip())
            except ValueError:
                continue
            if not 0 <= weekday <= LAST_WEEKDAY:
                continue
            start_time = _parse_time(row.get("START_TIME", ""))
            end_time = _parse_time(row.get("END_TIME", ""))
            if start_time is None or end_time is None:
                continue
            if start_time >= end_time:
                continue
            windows.append(
                ScheduleWindow(
                    weekday=weekday,
                    start_hour=start_time[0],
                    start_minute=start_time[1],
                    end_hour=end_time[0],
                    end_minute=end_time[1],
                )
            )
    return sorted(
        windows,
        key=lambda window: (
            window.weekday,
            window.start_hour,
            window.start_minute,
            window.end_hour,
            window.end_minute,
        ),
    )


def normalize_allowed_weekdays(
    allowed_weekdays: Iterable[int] | None,
    *,
    default: set[int] | frozenset[int] = DEFAULT_WEEKDAYS,
) -> set[int]:
    """Validate weekday numbers and fall back to the default send days."""
    if not allowed_weekdays:
        return set(default)
    return {day for day in allowed_weekdays if 0 <= day <= LAST_WEEKDAY} or set(default)


def parse_allowed_weekdays(
    raw: str | None,
    *,
    default: set[int] | frozenset[int] = DEFAULT_WEEKDAYS,
) -> set[int]:
    """Parse a comma-separated weekday list into validated integers."""
    allowed: list[int] = []
    for token in (raw or "").split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            day = int(stripped)
        except ValueError:
            continue
        allowed.append(day)
    return normalize_allowed_weekdays(allowed, default=default)


def env_timezone(*env_names: str, default: str) -> str:
    """Return the first non-empty timezone configured in env."""
    for env_name in env_names:
        value = os.getenv(env_name)
        if value:
            return value
    return default


def env_spacing_minutes(env_name: str, *, default: int) -> int:
    """Return a positive minute value from env."""
    return max(int(os.getenv(env_name, str(default))), 1)


def day_window_ranges(  # noqa: PLR0913
    timestamp: datetime,
    *,
    timezone: str,
    allowed_weekdays: set[int] | frozenset[int],
    start_hour: int = 9,
    start_minute: int = 0,
    end_hour: int = 16,
    end_minute: int = 30,
    schedule_csv_path: str | Path | None = None,
) -> list[tuple[datetime, datetime]]:
    """Return active local send ranges for the timestamp's weekday."""
    localized = timestamp.astimezone(ZoneInfo(timezone))
    schedule_windows = load_schedule_windows(schedule_csv_path)
    if schedule_windows:
        return [
            (
                localized.replace(
                    hour=window.start_hour,
                    minute=window.start_minute,
                    second=0,
                    microsecond=0,
                ),
                localized.replace(
                    hour=window.end_hour,
                    minute=window.end_minute,
                    second=0,
                    microsecond=0,
                ),
            )
            for window in schedule_windows
            if window.weekday == localized.weekday()
        ]

    if localized.weekday() not in normalize_allowed_weekdays(allowed_weekdays):
        return []

    return [
        (
            localized.replace(
                hour=start_hour,
                minute=start_minute,
                second=0,
                microsecond=0,
            ),
            localized.replace(
                hour=end_hour,
                minute=end_minute,
                second=0,
                microsecond=0,
            ),
        )
    ]


def within_send_window(  # noqa: PLR0913
    timestamp: datetime,
    *,
    timezone: str,
    allowed_weekdays: set[int] | frozenset[int],
    start_hour: int = 9,
    start_minute: int = 0,
    end_hour: int = 16,
    end_minute: int = 30,
    schedule_csv_path: str | Path | None = None,
) -> bool:
    """Return whether a timestamp is inside the allowed local send window."""
    localized = timestamp.astimezone(ZoneInfo(timezone))
    return any(
        window_start <= localized < window_end
        for window_start, window_end in day_window_ranges(
            timestamp,
            timezone=timezone,
            allowed_weekdays=allowed_weekdays,
            start_hour=start_hour,
            start_minute=start_minute,
            end_hour=end_hour,
            end_minute=end_minute,
            schedule_csv_path=schedule_csv_path,
        )
    )


def sleep_until(send_time: datetime) -> None:
    """Block until a scheduled send time arrives."""
    remaining = (send_time - datetime.now(send_time.tzinfo)).total_seconds()
    if remaining > 0:
        time.sleep(remaining)
