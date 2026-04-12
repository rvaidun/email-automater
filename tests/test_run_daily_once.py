"""Tests for the once-per-day scheduled runner."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import run_daily_once
from utils.outreach_state import OutreachStateStore


def _append_daily_run(
    store: OutreachStateStore,
    timestamp: datetime,
    *,
    dry_run: bool = False,
) -> None:
    """Persist one daily run record for scheduler assertions."""
    store.append_run(
        {
            "started_at": timestamp.isoformat(),
            "finished_at": timestamp.isoformat(),
            "mode": "daily",
            "dry_run": dry_run,
        }
    )
    store.save()


def test_already_completed_today_ignores_dry_runs(tmp_path):
    """Only real daily runs should block the scheduler."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    _append_daily_run(store, now, dry_run=True)

    assert run_daily_once._already_completed_today(store, now=now) is False  # noqa: SLF001


def test_already_completed_today_matches_finished_date(tmp_path):
    """A completed real run on the same day should be skipped."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    _append_daily_run(store, now)

    assert run_daily_once._already_completed_today(store, now=now) is True  # noqa: SLF001


def test_already_completed_today_ignores_pre_3pm_run_for_3pm_slot(tmp_path):
    """A manual run before the 3 PM scheduler should not block the 3 PM run."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    earlier_run = datetime(2026, 4, 12, 10, 16, tzinfo=ZoneInfo("America/New_York"))
    scheduler_time = datetime(2026, 4, 12, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    _append_daily_run(store, earlier_run)

    assert run_daily_once._already_completed_today(store, now=scheduler_time) is False  # noqa: SLF001


def test_already_completed_today_still_blocks_duplicate_before_3pm(tmp_path):
    """A same-day run should still block another run before the scheduler slot."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    earlier_run = datetime(2026, 4, 12, 10, 16, tzinfo=ZoneInfo("America/New_York"))
    check_time = datetime(2026, 4, 12, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    _append_daily_run(store, earlier_run)

    assert run_daily_once._already_completed_today(store, now=check_time) is True  # noqa: SLF001


def test_resolve_repo_path_keeps_absolute_paths():
    """Absolute paths should be preserved."""
    absolute = Path("/private") / "tmp" / "outreach_state.json"

    assert run_daily_once._resolve_repo_path(absolute) == absolute  # noqa: SLF001


def test_main_runs_pipeline_once_when_not_yet_completed(monkeypatch, tmp_path):
    """The scheduler should invoke pipeline.py once when today's run is still due."""
    now = datetime(2026, 4, 13, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"
    lock_path = tmp_path / "daily_pipeline.lock"
    invoked: dict[str, object] = {}

    monkeypatch.setattr(run_daily_once, "_now", lambda: now)
    monkeypatch.setattr(run_daily_once, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_daily_once, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(state_path))
    monkeypatch.setenv("PIPELINE_LOCK_PATH", str(lock_path))

    def fake_run(command: list[object], *, cwd: Path, check: bool) -> SimpleNamespace:
        invoked["command"] = command
        invoked["cwd"] = cwd
        invoked["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_daily_once.subprocess, "run", fake_run)

    result = run_daily_once.main()

    assert result == 0
    assert invoked["cwd"] == tmp_path
    assert invoked["check"] is False
    assert invoked["command"] == [
        run_daily_once.sys.executable,
        "pipeline.py",
        "--mode",
        "daily",
        "--state-path",
        state_path.resolve(),
    ]


def test_main_skips_pipeline_when_today_already_completed(
    monkeypatch,
    tmp_path,
    capsys,
):
    """The scheduler should not invoke pipeline twice on the same day."""
    now = datetime(2026, 4, 13, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"
    lock_path = tmp_path / "daily_pipeline.lock"
    store = OutreachStateStore(state_path)
    _append_daily_run(store, now)

    monkeypatch.setattr(run_daily_once, "_now", lambda: now)
    monkeypatch.setattr(run_daily_once, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_daily_once, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(state_path))
    monkeypatch.setenv("PIPELINE_LOCK_PATH", str(lock_path))
    monkeypatch.setattr(
        run_daily_once.subprocess,
        "run",
        lambda *_, **__: (_ for _ in ()).throw(
            AssertionError("subprocess.run should not be called")
        ),
    )

    result = run_daily_once.main()

    captured = capsys.readouterr().out
    assert result == 0
    assert "already completed" in captured


def test_main_skips_unscheduled_saturday(monkeypatch, tmp_path, capsys):
    """Saturday should be skipped before the pipeline subprocess is invoked."""
    now = datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"
    lock_path = tmp_path / "daily_pipeline.lock"

    monkeypatch.setattr(run_daily_once, "_now", lambda: now)
    monkeypatch.setattr(run_daily_once, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_daily_once, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("OUTREACH_STATE_PATH", str(state_path))
    monkeypatch.setenv("PIPELINE_LOCK_PATH", str(lock_path))
    monkeypatch.setattr(
        run_daily_once.subprocess,
        "run",
        lambda *_, **__: (_ for _ in ()).throw(
            AssertionError("subprocess.run should not be called")
        ),
    )

    result = run_daily_once.main()

    captured = capsys.readouterr().out
    assert result == 0
    assert "No scheduled pipeline run on Saturday" in captured
