"""Tests for scheduler weekday selection."""

from datetime import datetime

from utils import daily_schedule


def test_scheduled_weekdays_default_keeps_sunday_and_skips_saturday():
    """Default scheduled weekdays should be Sunday-Friday only."""
    weekdays = daily_schedule.scheduled_weekdays()

    assert weekdays == [0, 1, 2, 3, 4, 6]


def test_scheduled_weekdays_follow_custom_schedule_csv(tmp_path):
    """Custom scheduler.csv rows should control allowed scheduled weekdays."""
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n6,09:00,16:30\n")

    weekdays = daily_schedule.scheduled_weekdays(schedule_path)

    assert weekdays == [6]
    assert daily_schedule.cron_fields(schedule_path) == "0 15 * * 0"


def test_should_run_today_uses_scheduler_csv(tmp_path):
    """Saturday should be skipped when it has no scheduler.csv row."""
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n6,09:00,16:30\n")
    saturday = datetime(2026, 4, 11, 15, 0)
    sunday = datetime(2026, 4, 12, 15, 0)

    assert (
        daily_schedule.should_run_today(saturday, schedule_csv_path=schedule_path)
        is False
    )
    assert (
        daily_schedule.should_run_today(sunday, schedule_csv_path=schedule_path) is True
    )
