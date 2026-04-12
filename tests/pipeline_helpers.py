"""Shared helpers for daily pipeline tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scrape_jobs import ScrapedCompany


def make_scraped_company(
    now: datetime,
    *,
    display_name: str = "Stripe",
    company_key: str = "stripe",
    job_title: str = "Software Engineer",
    listing_url: str = "https://example.com/job",
) -> ScrapedCompany:
    """Build one scraped company fixture with consistent defaults."""
    return ScrapedCompany(
        display_name=display_name,
        company_key=company_key,
        job_title=job_title,
        listing_url=listing_url,
        posted_at=now.isoformat(),
    )


def make_single_company_scraper(
    now: datetime,
    **company_overrides: str,
) -> Any:
    """Return a scraper stub that yields one company."""
    company = make_scraped_company(now, **company_overrides)
    return lambda **_: [company]


def make_followup_summary(
    *,
    followups_sent: int = 0,
    replies_detected: int = 0,
    bounces_detected: int = 0,
) -> dict[str, int]:
    """Return the pipeline's follow-up summary fragment."""
    return {
        "followups_sent": followups_sent,
        "replies_detected": replies_detected,
        "bounces_detected": bounces_detected,
    }


def make_daily_args(
    tmp_path: Path,
    *,
    dry_run: bool,
    allow_paid_apollo_in_dry_run: bool,
    limit: int = 50,
    state_path: str | Path | None = None,
    apollo_api_key: str | None = "test-key",
    token_path: str | Path | None = None,
    creds_path: str | Path | None = None,
    token_name: str = "fake-token.json",
    creds_name: str = "fake-creds.json",
    screenshot: str | Path | None = None,
) -> SimpleNamespace:
    """Build a consistent argparse-like namespace for pipeline tests."""
    resolved_state = str(state_path or (tmp_path / "outreach_state.json"))
    resolved_token = str(token_path or (tmp_path / token_name))
    resolved_creds = str(creds_path or (tmp_path / creds_name))
    return SimpleNamespace(
        mode="daily",
        dry_run=dry_run,
        allow_paid_apollo_in_dry_run=allow_paid_apollo_in_dry_run,
        screenshot=screenshot,
        limit=limit,
        state_path=resolved_state,
        apollo_api_key=apollo_api_key,
        token_path=resolved_token,
        creds_path=resolved_creds,
    )
