"""Tests for cron setup helpers."""

from pathlib import Path

from utils.cron_setup import _merge_crontab_text, build_daily_pipeline_cron_line
from utils.daily_schedule import cron_fields


def test_merge_crontab_text_replaces_legacy_repo_entry():
    """The merge step should drop repo-local followup-only cron jobs."""
    repo_path = Path("/tmp/email-automater-2")
    resolved_repo = repo_path.expanduser().resolve()
    cron_line = build_daily_pipeline_cron_line(repo_path)
    existing = (
        "0 10 * * * cd /tmp/email-automater-1 && "
        "/tmp/email-automater-1/run_followups.sh\n"
        "# keep this comment\n"
        f"0 10 * * * cd {resolved_repo} && "
        f"{resolved_repo}/run_followups.sh\n"
    )

    merged = _merge_crontab_text(existing, repo_path=repo_path, cron_line=cron_line)

    assert "email-automater-1/run_followups.sh" in merged
    assert "email-automater-2/run_followups.sh" not in merged
    assert cron_line in merged
    assert cron_line.startswith(f"{cron_fields()} ")


def test_merge_crontab_text_dedupes_existing_pipeline_entry():
    """The merge step should not duplicate an already-installed pipeline cron."""
    repo_path = Path("/tmp/email-automater-2")
    cron_line = build_daily_pipeline_cron_line(repo_path)

    merged = _merge_crontab_text(
        f"{cron_line}\n",
        repo_path=repo_path,
        cron_line=cron_line,
    )

    assert merged == f"{cron_line}\n"
