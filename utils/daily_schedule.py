"""Shared schedule constants for the daily outreach run."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from utils.send_window import load_schedule_windows

if TYPE_CHECKING:
    from datetime import datetime

DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_SCHEDULE_CSV_PATH = "scheduler.csv"
DAILY_RUN_HOUR = 15
DAILY_RUN_MINUTE = 0
DEFAULT_LAUNCH_WEEKDAYS = frozenset({0, 1, 2, 3, 4, 6})


def scheduled_run_start(now: datetime) -> datetime:
    """Return the daily run slot in the caller's current timezone."""
    return now.replace(
        hour=DAILY_RUN_HOUR,
        minute=DAILY_RUN_MINUTE,
        second=0,
        microsecond=0,
    )


def _normalized_weekdays(weekdays: Iterable[int] | None) -> list[int]:
    """Return sorted Python weekdays with the default fallback."""
    normalized = sorted({day for day in weekdays or () if 0 <= day <= 6})
    return normalized or sorted(DEFAULT_LAUNCH_WEEKDAYS)


def scheduled_weekdays(
    schedule_csv_path: str | Path | None = None,
) -> list[int]:
    """Return Python weekday numbers allowed for the scheduled run."""
    windows = load_schedule_windows(schedule_csv_path)
    if not windows:
        return _normalized_weekdays(None)
    return _normalized_weekdays(window.weekday for window in windows)


def should_run_today(
    now: datetime,
    *,
    schedule_csv_path: str | Path | None = None,
) -> bool:
    """Return whether the scheduled runner should execute on this weekday."""
    return now.weekday() in scheduled_weekdays(schedule_csv_path)


def _cron_weekdays(schedule_csv_path: str | Path | None = None) -> list[int]:
    """Map Python weekdays to cron/launchd weekday numbers."""
    return [0 if day == 6 else day + 1 for day in scheduled_weekdays(schedule_csv_path)]


def cron_fields(schedule_csv_path: str | Path | None = None) -> str:
    """Return the cron expression prefix for the scheduled run slot."""
    weekdays = ",".join(str(day) for day in _cron_weekdays(schedule_csv_path))
    return f"{DAILY_RUN_MINUTE} {DAILY_RUN_HOUR} * * {weekdays}"


def launchd_weekdays(schedule_csv_path: str | Path | None = None) -> list[int]:
    """Return launchd weekday numbers for the scheduled run."""
    return _cron_weekdays(schedule_csv_path)
