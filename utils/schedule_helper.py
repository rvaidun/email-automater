"""Contains functions to help with scheduling emails."""

import csv
import datetime
import logging
import random
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


def parse_time_ranges_csv(
    csv_reader: csv.DictReader,
) -> list[list[tuple[datetime.time, datetime.time]]]:
    """
    Parse CSV data containing allowed time ranges and organize by day of week.

    Args:
        csv_reader: String containing CSV data with DAY, START_TIME, END_TIME columns

    Returns:
        List of 7 lists (one per day of week), in format (start_time, end_time)

    """
    # Initialize empty list for each day of the week (Monday-Sunday)
    day_ranges = [[] for _ in range(7)]

    for row in csv_reader:
        day = int(row["DAY"])

        # Parse start and end times
        start_hour, start_minute = map(int, row["START_TIME"].split(":"))
        end_hour, end_minute = map(int, row["END_TIME"].split(":"))

        start_time = datetime.time(start_hour, start_minute)
        end_time = datetime.time(end_hour, end_minute)

        # Add the time range to the appropriate day
        day_ranges[day].append((start_time, end_time))

    # Sort each day's ranges by start time
    for day in range(7):
        day_ranges[day].sort(key=lambda x: x[0])

    return day_ranges


def get_scheduled_send_time(
    day_ranges: list[list[tuple[datetime.time, datetime.time]]],
    timezone: str = "UTC",
    cur_time: datetime.datetime | None = None,
) -> bool | datetime.datetime:
    """
    Schedule an email based on current time and allowed ranges.

    Args:
        day_ranges: Data structure containing allowed time ranges for each day of the week
        timezone: Timezone to use for scheduling (e.g. "America/Los_Angeles")
        cur_time: Current time to use for scheduling (datetime object)

    Returns:
        True if current time is within an allowed range
        a datetime object for the next allowed time if found
        False if no allowed time ranges

    """  # noqa: E501
    now = cur_time or datetime.datetime.now(tz=ZoneInfo(timezone))

    # Parse the allowed time ranges

    # Get the current day and time
    current_day = now.weekday()
    current_time = now.time()

    time_range = None
    add_day = 0
    # Case 1: Check if current time is within an allowed range for today
    for start_time, end_time in day_ranges[current_day]:
        if start_time <= current_time < end_time:
            # Current time is in an allowed range, send with a small random delay
            return True
        if start_time > current_time:
            time_range = (start_time, end_time)
            break
    else:
        next_day = (current_day + 1) % 7
        while next_day != current_day:
            add_day += 1
            if day_ranges[next_day]:
                time_range = day_ranges[next_day][0]
                break
            next_day = (next_day + 1) % 7

        else:
            logger.info("No allowed time ranges found")
            return False

    # find a random time within the range
    start_time, end_time = time_range
    seconds_start = start_time.hour * 3600 + start_time.minute * 60
    seconds_end = end_time.hour * 3600 + end_time.minute * 60
    random_seconds = random.randint(seconds_start, seconds_end)  # noqa: S311 not for security
    random_time = datetime.time(random_seconds // 3600, (random_seconds % 3600) // 60)
    day = now.date() + datetime.timedelta(days=add_day)
    return datetime.datetime.combine(day, random_time, tzinfo=now.tzinfo)
