import datetime
from zoneinfo import ZoneInfo

from utils.schedule_helper import (
    paced_send_times,
)

LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")
SUNDAY_WEEKDAY = 6
PACED_SEND_COUNT = 6
FIRST_PACED_MINUTE = 5


def test_paced_send_times_can_send_on_sunday_when_allowed():
    """Sunday-enabled runs should stay on Sunday inside the current window."""
    now = datetime.datetime(2026, 4, 12, 15, 0, tzinfo=LOS_ANGELES_TZ)
    send_times = paced_send_times(
        2,
        now=now,
        timezone="America/Los_Angeles",
        allowed_weekdays={0, 1, 2, 3, 4, 6},
        minimum_spacing_minutes=15,
    )

    assert len(send_times) == 2
    assert all(send_time.weekday() == SUNDAY_WEEKDAY for send_time in send_times)


def test_paced_send_times_uses_fixed_gap_inside_current_window():
    """Conservative pacing should leave a visible gap between sends."""
    now = datetime.datetime(2026, 4, 10, 15, 0, tzinfo=LOS_ANGELES_TZ)
    send_times = paced_send_times(
        10,
        now=now,
        timezone="America/Los_Angeles",
        minimum_spacing_minutes=15,
    )

    assert len(send_times) == PACED_SEND_COUNT
    assert send_times[0].minute == FIRST_PACED_MINUTE
    assert send_times[1] - send_times[0] == datetime.timedelta(minutes=15)


def test_paced_send_times_can_use_editable_schedule_csv(tmp_path):
    """The pacing helper should honor same-day windows from scheduler.csv."""
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n6,14:30,16:30\n")
    now = datetime.datetime(2026, 4, 12, 15, 0, tzinfo=LOS_ANGELES_TZ)

    send_times = paced_send_times(
        3,
        now=now,
        timezone="America/Los_Angeles",
        allowed_weekdays={0, 1, 2, 3, 4},
        minimum_spacing_minutes=15,
        schedule_csv_path=str(schedule_path),
    )

    assert len(send_times) == 3
    assert all(send_time.weekday() == SUNDAY_WEEKDAY for send_time in send_times)
