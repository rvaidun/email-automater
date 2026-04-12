"""Error-path tests for the daily pipeline."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pipeline
from tests.pipeline_helpers import (
    make_daily_args,
    make_followup_summary,
    make_single_company_scraper,
)
from utils.apollo import ApolloQuotaError


def test_run_daily_without_apollo_key_returns_clean_summary(
    monkeypatch,
    tmp_path,
    capsys,
):
    """Missing Apollo should fail cleanly when live discovery is requested."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=True,
        state_path=state_path,
        apollo_api_key=None,
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 1
    assert "companies scraped: 1" in captured
    assert "contacts found: 0" in captured
    assert "new emails queued/sent: 0" in captured


def test_run_daily_stops_cleanly_on_apollo_quota(
    monkeypatch,
    tmp_path,
    capsys,
):
    """Apollo quota exhaustion should stop discovery without a traceback."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "ApolloClient",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        pipeline,
        "find_contacts_for_company",
        lambda *_, **__: (_ for _ in ()).throw(ApolloQuotaError("quota hit")),
    )
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=True,
        state_path=state_path,
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 1
    assert "companies scraped: 1" in captured
    assert "contacts found: 0" in captured
