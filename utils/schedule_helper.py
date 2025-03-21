"""Contains functions to help with scheduling emails."""

import datetime
import random
from zoneinfo import ZoneInfo

LOS_ANGELES_TZ = ZoneInfo("America/Los_Angeles")


def get_allowed_date_ranges(
    now: datetime.datetime,
) -> list[tuple[datetime.datetime, datetime.datetime]]:
    """
    Generate the allowed date ranges for the current week and next week.

    Allowed times are:
    - Monday-Thursday: 10:00 AM - 11:00 AM
    - Monday-Thursday: 2:00 PM - 2:30 PM

    Args:
        now: Current datetime in Pacific timezone

    Returns:
        List of (start_time, end_time) tuples representing allowed ranges

    """
    # Get the start of the current week (Monday)
    days_since_monday = now.weekday()
    monday = (now - datetime.timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Create all allowed ranges for this week and next week
    allowed_ranges = []

    # Generate ranges for two weeks (current and next)
    for week_offset in range(2):
        week_start = monday + datetime.timedelta(days=7 * week_offset)

        # For each Monday-Thursday
        for day_offset in range(4):  # 0=Monday through 3=Thursday
            day_start = week_start + datetime.timedelta(days=day_offset)

            # Morning range: 10:00 AM - 11:00 AM
            morning_start = day_start.replace(hour=10, minute=0)
            morning_end = day_start.replace(hour=11, minute=0)
            allowed_ranges.append((morning_start, morning_end))

            # Afternoon range: 2:00 PM - 2:30 PM
            afternoon_start = day_start.replace(hour=14, minute=0)
            afternoon_end = day_start.replace(hour=14, minute=30)
            allowed_ranges.append((afternoon_start, afternoon_end))

    # add a range for Friday between 10:00 AM and 11:00 AM
    friday = monday + datetime.timedelta(days=4)
    friday_morning_start = friday.replace(hour=10, minute=0)
    friday_morning_end = friday.replace(hour=11, minute=0)
    allowed_ranges.append((friday_morning_start, friday_morning_end))

    return allowed_ranges


def find_current_range(now: datetime.datetime,
                       allowed_ranges: list[tuple[datetime.datetime,
                                                  datetime.datetime]]
                       ) -> tuple[datetime.datetime, datetime.datetime] | None:
    """
    Check if current time falls within any allowed range.

    Args:
        now: Current datetime
        allowed_ranges: List of (start_time, end_time) tuples

    Returns:
        The current range tuple if found, None otherwise

    """
    for start_time, end_time in allowed_ranges:
        if start_time <= now < end_time:
            return (start_time, end_time)
    return None


def find_next_range(now: datetime.datetime,
                    allowed_ranges: list[tuple[datetime.datetime,
                                               datetime.datetime]]
                    ) -> tuple[datetime.datetime, datetime.datetime]:
    """
    Find the next allowed range after the current time.

    Args:
        now: Current datetime
        allowed_ranges: List of (start_time, end_time) tuples

    Returns:
        The next range tuple

    """
    future_ranges = [(start, end)
                     for start, end in allowed_ranges if start > now]
    future_ranges.sort(key=lambda x: x[0])  # Sort by start time
    return future_ranges[0]  # Return the earliest future range


def get_scheduled_send_time() -> datetime.datetime | bool:
    """
    Schedule an email based on current time in Pacific timezone.

    Uses predefined allowed time ranges for sending emails.

    Returns:
        Tuple containing:
        - scheduled_time: datetime object with the calculated send time
        - reason: string explaining why that time was chosen

    """
    # Get current time in Pacific timezone
    now = datetime.datetime.now(tz=LOS_ANGELES_TZ)

    # Define the allowed date ranges for sending emails (Monday-Thursday only)
    allowed_ranges = get_allowed_date_ranges(now)

    # Check if current time is within an allowed range
    current_range = find_current_range(now, allowed_ranges)

    if current_range:
        # If we're in an allowed range, send immediately at a random time within
        # (simulating "send now" but with a small randomization)
        return True
    # Find the next available range
    next_range = find_next_range(now, allowed_ranges)

    # Schedule at a random time within the next available range
    start_time, end_time = next_range
    range_seconds = int((end_time - start_time).total_seconds())
    random_seconds = random.randint(0, range_seconds)  # noqa: S311 we are not doing this for security purposes
    return start_time + datetime.timedelta(seconds=random_seconds)
