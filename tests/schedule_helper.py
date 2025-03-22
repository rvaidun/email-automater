import csv
import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest

from utils.schedule_helper import get_scheduled_send_time, parse_time_ranges_csv

LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


def test_parse_time_ranges_csv():
    csv_data = """DAY,START_TIME,END_TIME
0,09:00,12:00
0,13:00,15:00
1,10:00,14:00
"""
    csv_reader = csv.DictReader(StringIO(csv_data))
    result = parse_time_ranges_csv(csv_reader)

    assert len(result) == 7
    assert result[0] == [
        (datetime.time(9, 0), datetime.time(12, 0)),
        (datetime.time(13, 0), datetime.time(15, 0)),
    ]
    assert result[1] == [(datetime.time(10, 0), datetime.time(14, 0))]
    assert result[2] == []
    assert result[6] == []


def test_get_scheduled_send_time_within_range():
    csv_data = """DAY,START_TIME,END_TIME
0,09:00,12:00
"""
    csv_reader = csv.DictReader(StringIO(csv_data))
    now = datetime.datetime(2023, 3, 6, 10, 0, tzinfo=LOS_ANGELES_TZ)  # Monday
    result = get_scheduled_send_time(csv_reader, "America/Los_Angeles")

    assert result is True


def test_get_scheduled_send_time_outside_range():
    csv_data = """DAY,START_TIME,END_TIME
0,09:00,12:00
"""
    csv_reader = csv.DictReader(StringIO(csv_data))
    now = datetime.datetime(2023, 3, 6, 13, 0, tzinfo=LOS_ANGELES_TZ)  # Monday
    result = get_scheduled_send_time(csv_reader, "America/Los_Angeles")

    assert result is False
