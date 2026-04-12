"""Cron helpers for the daily outreach pipeline."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from utils.daily_schedule import DEFAULT_SCHEDULE_CSV_PATH, cron_fields

logger = logging.getLogger(__name__)


def build_daily_pipeline_cron_line(
    repo_path: str | Path,
    *,
    python_path: str | Path | None = None,
    log_path: str | Path | None = None,
    schedule_csv_path: str | Path | None = None,
) -> str:
    """Return the daily cron line for the locked once-only runner."""
    repo_path = Path(repo_path).expanduser().resolve()
    resolved_python = (
        Path(python_path).expanduser().resolve()
        if python_path
        else repo_path / ".venv/bin/python"
    )
    resolved_log = (
        Path(log_path).expanduser().resolve()
        if log_path
        else repo_path / "daily_run.log"
    )
    resolved_schedule = (
        Path(schedule_csv_path).expanduser().resolve()
        if schedule_csv_path
        else repo_path / DEFAULT_SCHEDULE_CSV_PATH
    )
    return (
        f"{cron_fields(resolved_schedule)} cd {repo_path} && {resolved_python} "
        f"run_daily_once.py >> {resolved_log} 2>&1"
    )


def _merge_crontab_text(existing: str, *, repo_path: Path, cron_line: str) -> str:
    """Replace repo-local legacy jobs with the pipeline entry."""
    resolved_repo = str(repo_path.expanduser().resolve())
    updated_lines: list[str] = []

    for line in existing.splitlines():
        stripped = line.strip()
        if not stripped:
            if updated_lines and updated_lines[-1]:
                updated_lines.append("")
            continue
        if stripped.startswith("#"):
            updated_lines.append(line)
            continue
        if resolved_repo not in line:
            updated_lines.append(line)
            continue
        if "run_followups.sh" in line or "pipeline.py --mode daily" in line:
            continue
        updated_lines.append(line)

    while updated_lines and not updated_lines[-1]:
        updated_lines.pop()

    if cron_line not in updated_lines:
        updated_lines.append(cron_line)
    return "\n".join(updated_lines) + "\n"


def setup_pipeline_cron_job(
    repo_path: str | Path,
    *,
    python_path: str | Path | None = None,
    log_path: str | Path | None = None,
    schedule_csv_path: str | Path | None = None,
) -> bool:
    """Install the daily pipeline cron job if it is not already present."""
    resolved_repo = Path(repo_path).expanduser().resolve()
    cron_line = build_daily_pipeline_cron_line(
        resolved_repo,
        python_path=python_path,
        log_path=log_path,
        schedule_csv_path=schedule_csv_path,
    )
    crontab_path = shutil.which("crontab")
    if not crontab_path:
        logger.error("crontab is not available on PATH")
        return False

    current = subprocess.run(  # noqa: S603
        [crontab_path, "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    existing = current.stdout if current.returncode == 0 else ""
    merged = _merge_crontab_text(existing, repo_path=resolved_repo, cron_line=cron_line)
    if merged == existing:
        logger.info("Daily pipeline cron job already installed")
        return True

    updated = subprocess.run(  # noqa: S603
        [crontab_path, "-"],
        input=merged,
        capture_output=True,
        text=True,
        check=False,
    )
    if updated.returncode != 0:
        logger.error("Failed to install cron job: %s", updated.stderr.strip())
        return False

    logger.info("Installed daily pipeline cron job")
    return True


def parse_args() -> argparse.Namespace:
    """Parse CLI args for cron setup."""
    parser = argparse.ArgumentParser(description="Install the daily pipeline cron job")
    parser.add_argument(
        "--repo-path",
        default=Path.cwd(),
        help="Repository root containing pipeline.py",
    )
    parser.add_argument(
        "--python-path",
        default=None,
        help="Python interpreter used by cron",
    )
    parser.add_argument(
        "--log-path",
        default=None,
        help="Log file written by cron",
    )
    parser.add_argument(
        "--schedule-csv-path",
        default=None,
        help="Optional scheduler.csv path used to choose active weekdays",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the cron line without installing it",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    cron_line = build_daily_pipeline_cron_line(
        args.repo_path,
        python_path=args.python_path,
        log_path=args.log_path,
        schedule_csv_path=args.schedule_csv_path,
    )
    if args.print_only:
        sys.stdout.write(f"{cron_line}\n")
        return 0
    return (
        0
        if setup_pipeline_cron_job(
            args.repo_path,
            python_path=args.python_path,
            log_path=args.log_path,
            schedule_csv_path=args.schedule_csv_path,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
