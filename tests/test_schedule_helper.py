import csv
import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest

from utils.schedule_helper import get_scheduled_send_time, parse_time_ranges_csv


@pytest.fixture(autouse=True)
def csv_data():
    """Return a CSV string with allowed time ranges."""
    return """DAY,START_TIME,END_TIME
0, 10:00, 11:00
0, 14:00, 14:30
1, 10:00, 11:00
1, 14:00, 14:30
2, 10:00, 11:00
2, 14:00, 14:30
3, 10:00, 11:00
3, 14:00, 14:30
4, 10:00, 11:00
"""


LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


def test_parse_time_ranges_csv():
    """Test that the function correctly parses CSV data into a list of time ranges."""
    csv_data = """DAY,START_TIME,END_TIME
0,09:00,12:00
0,13:00,15:00
1,10:00,14:00
"""
    csv_reader = csv.DictReader(StringIO(csv_data))
    result = parse_time_ranges_csv(csv_reader)

    assert len(result) == 7  # noqa: PLR2004
    assert result[0] == [
        (datetime.time(9, 0), datetime.time(12, 0)),
        (datetime.time(13, 0), datetime.time(15, 0)),
    ]
    assert result[1] == [(datetime.time(10, 0), datetime.time(14, 0))]
    assert result[2] == []
    assert result[6] == []


def test_get_scheduled_send_time_within_range(csv_data):
    """Correctly schedules an email within an allowed time range."""
    csv_reader = csv.DictReader(StringIO(csv_data))
    parsed_csv = parse_time_ranges_csv(csv_reader)
    dates = [
        (
            datetime.datetime(2025, 3, 18, 9, 15, tzinfo=LOS_ANGELES_TZ),
            (
                datetime.datetime(2025, 3, 18, 10, 00, tzinfo=LOS_ANGELES_TZ),
                datetime.datetime(2025, 3, 18, 11, 00, tzinfo=LOS_ANGELES_TZ),
            ),
        ),  # Monday 9:15 AM - returns between 10:00 AM and 11:00 AM
        (
            datetime.datetime(2025, 3, 18, 10, 30, tzinfo=LOS_ANGELES_TZ),
            True,
        ),  # Monday 10:30 AM - returns True since in range
        (
            datetime.datetime(2025, 3, 18, 12, 15, tzinfo=LOS_ANGELES_TZ),
            (
                datetime.datetime(2025, 3, 18, 14, 00, tzinfo=LOS_ANGELES_TZ),
                datetime.datetime(2025, 3, 18, 14, 30, tzinfo=LOS_ANGELES_TZ),
            ),
        ),  # Monday 12:15 PM - returns between 2:00 PM and 2:30
        (
            datetime.datetime(2025, 3, 18, 15, 00, tzinfo=LOS_ANGELES_TZ),
            (
                datetime.datetime(2025, 3, 19, 10, 00, tzinfo=LOS_ANGELES_TZ),
                datetime.datetime(2025, 3, 19, 11, 00, tzinfo=LOS_ANGELES_TZ),
            ),
        ),  # Monday 3:00 PM - returns between 10:00 AM and 11:00 AM next day
        (
            datetime.datetime(2025, 3, 21, 18, 00, tzinfo=LOS_ANGELES_TZ),
            (
                datetime.datetime(2025, 3, 24, 10, 00, tzinfo=LOS_ANGELES_TZ),
                datetime.datetime(2025, 3, 24, 11, 00, tzinfo=LOS_ANGELES_TZ),
            ),
        ),  # Friday 06:00 PM - returns between 10:00 AM and 11:00 AM next Monday
    ]

    for now, expected in dates:
        result = get_scheduled_send_time(parsed_csv, "America/Los_Angeles", now)
        if isinstance(expected, bool):
            assert result is expected
        else:
            assert expected[0] <= result < expected[1]
