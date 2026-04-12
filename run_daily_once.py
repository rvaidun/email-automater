"""Run the daily pipeline at most once per day for local schedulers."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from utils.daily_schedule import (
    DEFAULT_SCHEDULE_CSV_PATH,
    DEFAULT_TIMEZONE,
    scheduled_run_start,
    should_run_today,
)
from utils.outreach_state import OutreachStateStore, parse_datetime

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path("state/outreach_state.json")
DEFAULT_LOCK_PATH = Path("state/daily_pipeline.lock")


def _resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _now() -> datetime:
    return datetime.now(ZoneInfo(os.getenv("TIMEZONE", DEFAULT_TIMEZONE)))


def _scheduled_run_start(now: datetime) -> datetime:
    """Return today's scheduler slot in the current local timezone."""
    return scheduled_run_start(now)


def _already_completed_today(
    store: OutreachStateStore,
    *,
    now: datetime,
) -> bool:
    scheduled_start = _scheduled_run_start(now)
    for run in reversed(store.runs):
        if run.get("mode") != "daily" or run.get("dry_run"):
            continue
        timestamp = parse_datetime(run.get("finished_at")) or parse_datetime(
            run.get("started_at")
        )
        if timestamp is None:
            continue
        localized = timestamp.astimezone(now.tzinfo)
        if localized.date() != now.date():
            continue
        if now >= scheduled_start and localized < scheduled_start:
            continue
        if localized.date() == now.date():
            return True
    return False


def main() -> int:
    """Run the pipeline once for the current day."""
    load_dotenv(dotenv_path=REPO_ROOT / ".env")
    state_path = _resolve_repo_path(
        os.getenv("OUTREACH_STATE_PATH", str(DEFAULT_STATE_PATH))
    )
    lock_path = _resolve_repo_path(
        os.getenv("PIPELINE_LOCK_PATH", str(DEFAULT_LOCK_PATH))
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("w") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.stdout.write("Scheduled daily pipeline already running; skipping.\n")
            return 0

        now = _now()
        schedule_csv_value = (
            os.getenv("SCHEDULE_CSV_PATH", DEFAULT_SCHEDULE_CSV_PATH).strip()
            or DEFAULT_SCHEDULE_CSV_PATH
        )
        schedule_csv_path = _resolve_repo_path(schedule_csv_value)
        if not should_run_today(now, schedule_csv_path=schedule_csv_path):
            sys.stdout.write(
                f"No scheduled pipeline run on {now.strftime('%A')}; skipping.\n"
            )
            return 0
        state = OutreachStateStore(
            state_path,
            timezone=os.getenv("TIMEZONE", DEFAULT_TIMEZONE),
        )
        if _already_completed_today(state, now=now):
            sys.stdout.write(
                f"Daily pipeline already completed on {now.date().isoformat()}; "
                "skipping.\n"
            )
            return 0

        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "pipeline.py",
                "--mode",
                "daily",
                "--state-path",
                state_path,
            ],
            cwd=REPO_ROOT,
            check=False,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
