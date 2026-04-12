"""Tests for the launchd installer helpers."""

from pathlib import Path

from utils.daily_schedule import DAILY_RUN_HOUR, DAILY_RUN_MINUTE
from utils.launchd_setup import build_daily_pipeline_launch_agent, launch_agent_path


def test_build_daily_pipeline_launch_agent_points_to_once_runner():
    """The LaunchAgent should invoke the once-per-day wrapper at 3 PM."""
    repo_path = Path("/tmp/email-automater-2")

    plist = build_daily_pipeline_launch_agent(repo_path)

    assert "run_daily_once.py" in plist
    assert f"<integer>{DAILY_RUN_HOUR}</integer>" in plist
    assert f"<integer>{DAILY_RUN_MINUTE}</integer>" in plist
    assert plist.count("<key>Weekday</key>") == 6  # Sunday-Friday
    assert "<integer>6</integer>" not in plist  # Saturday not scheduled
    assert "daily_run.log" in plist


def test_launch_agent_path_uses_label_filename(tmp_path):
    """The plist path should be derived from the LaunchAgent label."""
    path = launch_agent_path(
        label="com.example.pipeline",
        launch_agents_dir=tmp_path,
    )

    assert path == tmp_path / "com.example.pipeline.plist"


def test_build_daily_pipeline_launch_agent_uses_custom_schedule_csv(tmp_path):
    """A custom scheduler.csv should narrow the LaunchAgent weekdays."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    schedule_path = tmp_path / "scheduler.csv"
    schedule_path.write_text("DAY,START_TIME,END_TIME\n6,09:00,16:30\n")

    plist = build_daily_pipeline_launch_agent(
        repo_path,
        schedule_csv_path=schedule_path,
    )

    assert plist.count("<key>Weekday</key>") == 1
