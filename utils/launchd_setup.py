"""LaunchAgent helpers for the daily outreach pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from utils.daily_schedule import DAILY_RUN_HOUR, DAILY_RUN_MINUTE

logger = logging.getLogger(__name__)

DEFAULT_LABEL = "com.emailautomater.daily"


class LaunchAgentInstallError(RuntimeError):
    """Raised when the daily LaunchAgent cannot be installed."""


def launch_agent_path(
    *,
    label: str = DEFAULT_LABEL,
    launch_agents_dir: str | Path | None = None,
) -> Path:
    """Return the LaunchAgent plist path."""
    base_dir = (
        Path(launch_agents_dir).expanduser().resolve()
        if launch_agents_dir
        else Path.home() / "Library/LaunchAgents"
    )
    return base_dir / f"{label}.plist"


def build_daily_pipeline_launch_agent(
    repo_path: str | Path,
    *,
    python_path: str | Path | None = None,
    log_path: str | Path | None = None,
    label: str = DEFAULT_LABEL,
) -> str:
    """Return a LaunchAgent plist for the daily once-only runner."""
    resolved_repo = Path(repo_path).expanduser().resolve()
    resolved_python = (
        Path(python_path).expanduser().resolve()
        if python_path
        else resolved_repo / ".venv/bin/python"
    )
    resolved_log = (
        Path(log_path).expanduser().resolve()
        if log_path
        else resolved_repo / "daily_run.log"
    )
    runner_path = resolved_repo / "run_daily_once.py"

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            "<dict>",
            "  <key>Label</key>",
            f"  <string>{escape(label)}</string>",
            "  <key>ProgramArguments</key>",
            "  <array>",
            f"    <string>{escape(str(resolved_python))}</string>",
            f"    <string>{escape(str(runner_path))}</string>",
            "  </array>",
            "  <key>WorkingDirectory</key>",
            f"  <string>{escape(str(resolved_repo))}</string>",
            "  <key>StartCalendarInterval</key>",
            "  <dict>",
            "    <key>Hour</key>",
            f"    <integer>{DAILY_RUN_HOUR}</integer>",
            "    <key>Minute</key>",
            f"    <integer>{DAILY_RUN_MINUTE}</integer>",
            "  </dict>",
            "  <key>StandardOutPath</key>",
            f"  <string>{escape(str(resolved_log))}</string>",
            "  <key>StandardErrorPath</key>",
            f"  <string>{escape(str(resolved_log))}</string>",
            "</dict>",
            "</plist>",
            "",
        ]
    )


def install_launch_agent(
    repo_path: str | Path,
    *,
    python_path: str | Path | None = None,
    log_path: str | Path | None = None,
    label: str = DEFAULT_LABEL,
    launch_agents_dir: str | Path | None = None,
) -> Path:
    """Write and load the LaunchAgent plist."""
    plist_path = launch_agent_path(
        label=label,
        launch_agents_dir=launch_agents_dir,
    )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(
        build_daily_pipeline_launch_agent(
            repo_path,
            python_path=python_path,
            log_path=log_path,
            label=label,
        )
    )

    uid = os.getuid()
    launchctl_path = shutil.which("launchctl")
    if not launchctl_path:
        error_message = "launchctl is not available on PATH"
        raise LaunchAgentInstallError(error_message)
    subprocess.run(  # noqa: S603
        [launchctl_path, "bootout", f"gui/{uid}", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    bootstrap = subprocess.run(  # noqa: S603
        [launchctl_path, "bootstrap", f"gui/{uid}", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if bootstrap.returncode != 0:
        msg = bootstrap.stderr.strip() or bootstrap.stdout.strip()
        error_message = f"Failed to bootstrap LaunchAgent: {msg}"
        raise LaunchAgentInstallError(error_message)
    return plist_path


def parse_args() -> argparse.Namespace:
    """Parse CLI args for launchd setup."""
    parser = argparse.ArgumentParser(
        description="Install the daily pipeline LaunchAgent"
    )
    parser.add_argument(
        "--repo-path",
        default=Path.cwd(),
        help="Repository root containing run_daily_once.py",
    )
    parser.add_argument(
        "--python-path",
        default=None,
        help="Python interpreter used by launchd",
    )
    parser.add_argument(
        "--log-path",
        default=None,
        help="Log file written by launchd",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the plist without installing it",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    if args.print_only:
        sys.stdout.write(
            build_daily_pipeline_launch_agent(
                args.repo_path,
                python_path=args.python_path,
                log_path=args.log_path,
            )
        )
        return 0

    try:
        install_launch_agent(
            args.repo_path,
            python_path=args.python_path,
            log_path=args.log_path,
        )
    except LaunchAgentInstallError:
        logger.exception("Failed to install daily LaunchAgent")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
