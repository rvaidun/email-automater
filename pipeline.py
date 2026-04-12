# ruff: noqa: PLR0913
"""Daily recruiter outreach pipeline."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from find_contacts import find_contacts_for_company
from scrape_jobs import scrape_companies
from send_followups import process_followups
from utils import outreach_delivery
from utils.apollo import ApolloClient
from utils.daily_pipeline_runtime import (
    DiscoveryPhase,
    RunPlan,
)
from utils.daily_pipeline_runtime import (
    build_run_plan as _build_run_plan_impl,
)
from utils.daily_pipeline_runtime import (
    discover_contacts as _discover_contacts_impl,
)
from utils.daily_pipeline_runtime import (
    run_discovery_phase as _run_discovery_phase_impl,
)
from utils.daily_pipeline_runtime import (
    select_companies as _select_companies_impl,
)
from utils.logging_setup import configure_logger
from utils.outreach_state import OutreachStateStore
from utils.send_window import (
    env_spacing_minutes,
    env_timezone,
    parse_allowed_weekdays,
)
from utils.send_window import (
    sleep_until as _sleep_until,
)
from utils.send_window import (
    within_send_window as _within_send_window,
)

load_dotenv()

logger = configure_logger(__name__)
_render_initial_email = outreach_delivery.render_initial_email

DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_SEND_WINDOW_TIMEZONE = "America/New_York"
DEFAULT_SCHEDULE_CSV_PATH = "scheduler.csv"
DEFAULT_LOCAL_SEND_MIN_SPACING_MINUTES = 15
DEFAULT_SEND_WEEKDAYS = "0,1,2,3,4"
DEFAULT_TITLE_KEYWORDS = (
    "software,cloud,backend,frontend,full stack,fullstack,platform,"
    "infra,infrastructure,devops,sre,site reliability"
)
DEFAULT_DAILY_OUTREACH_LIMIT = 15
DEFAULT_PIPELINE_CONTACT_DISCOVERY_LIMIT = 1
DAILY_TARGET = 50
DEFAULT_MAX_COMPANIES_PER_RUN = 50
DEFAULT_OUTREACH_WEEKDAYS = "0,1,2,3,4"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run the outreach pipeline")
    parser.add_argument(
        "--mode",
        choices=["daily"],
        required=True,
        help="Pipeline mode",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not send emails")
    parser.add_argument(
        "--allow-paid-apollo-in-dry-run",
        action="store_true",
        help=(
            "Opt into live Apollo discovery during --dry-run. Disabled by "
            "default to avoid spending paid credits."
        ),
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Fallback screenshot used only if scraping fails",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=_daily_outreach_limit(),
        help="New outreach emails to queue per run",
    )
    parser.add_argument(
        "--state-path",
        default="state/outreach_state.json",
        help="Primary outreach state file",
    )
    parser.add_argument(
        "--apollo-api-key",
        type=str,
        help="Apollo API key. Falls back to APOLLO_API_KEY.",
    )
    parser.add_argument(
        "--token-path",
        default=os.getenv("TOKEN_PATH", "token.json"),
        help="Path to Gmail token.json",
    )
    parser.add_argument(
        "--creds-path",
        default=os.getenv("CREDS_PATH", "credentials.json"),
        help="Path to Gmail credentials.json",
    )
    return parser.parse_args()


def _now() -> datetime:
    return datetime.now(ZoneInfo(os.getenv("TIMEZONE", DEFAULT_TIMEZONE)))


def _allowed_outreach_weekdays() -> set[int]:
    return parse_allowed_weekdays(
        os.getenv("OUTREACH_WEEKDAYS", DEFAULT_OUTREACH_WEEKDAYS)
    )


def _is_outreach_day(timestamp: datetime) -> bool:
    return timestamp.weekday() in _allowed_outreach_weekdays()


def _allowed_send_weekdays() -> set[int]:
    return parse_allowed_weekdays(
        os.getenv(
            "SEND_WEEKDAYS",
            os.getenv("OUTREACH_WEEKDAYS", DEFAULT_SEND_WEEKDAYS),
        )
    )


def _send_window_timezone() -> str:
    return env_timezone(
        "SEND_WINDOW_TIMEZONE",
        "TIMEZONE",
        default=DEFAULT_SEND_WINDOW_TIMEZONE,
    )


def _schedule_csv_path() -> str | None:
    raw = os.getenv("SCHEDULE_CSV_PATH", DEFAULT_SCHEDULE_CSV_PATH).strip()
    return raw or None


def _title_keywords() -> tuple[str, ...]:
    raw = os.getenv("JOB_TITLE_KEYWORDS", DEFAULT_TITLE_KEYWORDS)
    return tuple(
        keyword.strip().lower() for keyword in raw.split(",") if keyword.strip()
    )


def _title_matches(job_title: str) -> bool:
    lowered = job_title.strip().lower()
    keywords = _title_keywords()
    if not keywords:
        return True
    return any(keyword in lowered for keyword in keywords)


def _title_priority(job_title: str) -> int:
    """Prefer obvious software titles before broader infrastructure matches."""
    lowered = job_title.strip().lower()
    if "software engineer" in lowered:
        return 4
    if "software" in lowered:
        return 3
    if any(
        keyword in lowered
        for keyword in (
            "cloud",
            "backend",
            "frontend",
            "full stack",
            "fullstack",
            "platform",
            "infra",
            "infrastructure",
            "devops",
            "sre",
            "site reliability",
        )
    ):
        return 2
    return 1 if _title_matches(job_title) else 0


def _pipeline_contact_discovery_limit() -> int:
    raw_limit = os.getenv(
        "PIPELINE_CONTACT_DISCOVERY_LIMIT_PER_COMPANY",
        str(DEFAULT_PIPELINE_CONTACT_DISCOVERY_LIMIT),
    )
    return max(int(raw_limit), 1)


def _daily_outreach_limit() -> int:
    raw_limit = os.getenv(
        "NEW_OUTREACH_DAILY_LIMIT",
        str(DEFAULT_DAILY_OUTREACH_LIMIT),
    )
    return max(min(int(raw_limit), DAILY_TARGET), 0)


def _max_companies_per_run() -> int:
    raw_limit = os.getenv(
        "MAX_COMPANIES_PER_RUN",
        str(DEFAULT_MAX_COMPANIES_PER_RUN),
    )
    return max(int(raw_limit), 1)


def _local_send_min_spacing_minutes() -> int:
    """Return the minimum gap between immediate Gmail sends."""
    return env_spacing_minutes(
        "LOCAL_SEND_MIN_SPACING_MINUTES",
        default=DEFAULT_LOCAL_SEND_MIN_SPACING_MINUTES,
    )


def _can_queue_new_outreach(now: datetime) -> bool:
    """Only spend Apollo when we have a safe path to queue or send outreach."""
    return _within_send_window(
        now,
        timezone=_send_window_timezone(),
        allowed_weekdays=_allowed_send_weekdays(),
        schedule_csv_path=_schedule_csv_path(),
    )


def _summary_template(timestamp: datetime, *, dry_run: bool) -> dict[str, Any]:
    return {
        "started_at": timestamp.isoformat(),
        "finished_at": None,
        "mode": "daily",
        "dry_run": dry_run,
        "companies_scraped": 0,
        "companies_skipped_by_cooldown": 0,
        "contacts_found": 0,
        "contacts_skipped_as_duplicates": 0,
        "new_emails_queued_sent": 0,
        "followups_sent": 0,
        "replies_detected": 0,
        "bounces_detected": 0,
    }


def _select_companies(
    *,
    state: OutreachStateStore,
    now: datetime,
    screenshot: Path | None,
) -> tuple[list[Any], int, int]:
    return _select_companies_impl(
        state=state,
        now=now,
        screenshot=screenshot,
        scrape_companies=scrape_companies,
        title_matches=_title_matches,
        title_priority=_title_priority,
        max_companies_per_run=_max_companies_per_run(),
    )


def _discover_contacts(
    *,
    companies: list[Any],
    state: OutreachStateStore,
    apollo_client: ApolloClient,
    limit: int,
) -> tuple[list[dict[str, Any]], int, int, str | None]:
    return _discover_contacts_impl(
        companies=companies,
        state=state,
        apollo_client=apollo_client,
        limit=limit,
        per_company_limit=_pipeline_contact_discovery_limit(),
        find_contacts_for_company=find_contacts_for_company,
        logger=logger,
    )


def _build_run_plan(
    *,
    state: OutreachStateStore,
    started_at: datetime,
    limit: int,
) -> RunPlan:
    return _build_run_plan_impl(
        requested_limit=limit,
        daily_outreach_limit=_daily_outreach_limit(),
        already_actioned_today=state.new_outreach_actions_on_day(now=started_at),
        is_outreach_day=_is_outreach_day(started_at),
        can_queue_new_outreach=_can_queue_new_outreach(started_at),
    )


def _run_discovery_phase(
    *,
    args: argparse.Namespace,
    state: OutreachStateStore,
    started_at: datetime,
    plan: RunPlan,
) -> DiscoveryPhase:
    return _run_discovery_phase_impl(
        plan=plan,
        state=state,
        now=started_at,
        screenshot=args.screenshot,
        scrape_companies=scrape_companies,
        title_matches=_title_matches,
        title_priority=_title_priority,
        max_companies_per_run=_max_companies_per_run(),
        dry_run=args.dry_run,
        allow_paid_apollo_in_dry_run=bool(
            getattr(args, "allow_paid_apollo_in_dry_run", False)
        ),
        is_outreach_day=_is_outreach_day(started_at),
        apollo_api_key=args.apollo_api_key,
        apollo_client_factory=ApolloClient,
        find_contacts_for_company=find_contacts_for_company,
        per_company_limit=_pipeline_contact_discovery_limit(),
        logger=logger,
    )


def _queue_new_outreach(
    *,
    contacts: list[dict[str, Any]],
    state: OutreachStateStore,
    now: datetime,
    token_path: str,
    creds_path: str,
    dry_run: bool,
) -> tuple[int, str | None]:
    return outreach_delivery.queue_new_outreach(
        contacts=contacts,
        state=state,
        now=now,
        token_path=token_path,
        creds_path=creds_path,
        dry_run=dry_run,
        is_outreach_day=_is_outreach_day(now),
        send_window_timezone=_send_window_timezone(),
        allowed_send_weekdays=_allowed_send_weekdays(),
        local_send_min_spacing_minutes=_local_send_min_spacing_minutes(),
        schedule_csv_path=_schedule_csv_path(),
        now_provider=_now,
        sleep_until=_sleep_until,
    )


def print_summary(summary: dict[str, Any]) -> None:
    """Print the required run summary fields."""
    lines = [
        "Run Summary",
        f"companies scraped: {summary['companies_scraped']}",
        (f"companies skipped by cooldown: {summary['companies_skipped_by_cooldown']}"),
        f"contacts found: {summary['contacts_found']}",
        (
            "contacts skipped as duplicates: "
            f"{summary['contacts_skipped_as_duplicates']}"
        ),
        f"new emails queued/sent: {summary['new_emails_queued_sent']}",
        f"follow-ups sent: {summary['followups_sent']}",
        f"replies detected: {summary['replies_detected']}",
        f"bounces detected: {summary['bounces_detected']}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")


def run_daily(args: argparse.Namespace) -> int:
    """Run the daily pipeline mode."""
    started_at = _now()
    state = OutreachStateStore(
        args.state_path,
        timezone=os.getenv("TIMEZONE", DEFAULT_TIMEZONE),
    )
    summary = _summary_template(started_at, dry_run=args.dry_run)
    plan = _build_run_plan(
        state=state,
        started_at=started_at,
        limit=args.limit,
    )
    discovery = _run_discovery_phase(
        args=args,
        state=state,
        started_at=started_at,
        plan=plan,
    )
    summary["companies_scraped"] = discovery.scraped_count
    summary["companies_skipped_by_cooldown"] = discovery.skipped_count
    summary["contacts_found"] = discovery.contacts_found
    summary["contacts_skipped_as_duplicates"] = discovery.duplicates

    queue_count, new_send_error = _queue_new_outreach(
        contacts=discovery.contacts,
        state=state,
        now=started_at,
        token_path=args.token_path,
        creds_path=args.creds_path,
        dry_run=args.dry_run,
    )
    summary["new_emails_queued_sent"] = queue_count

    followup_summary = process_followups(
        state_path=args.state_path,
        token_path=args.token_path,
        creds_path=args.creds_path,
        dry_run=args.dry_run,
        state_store=state,
    )
    summary["followups_sent"] = followup_summary["followups_sent"]
    summary["replies_detected"] = followup_summary["replies_detected"]
    summary["bounces_detected"] = followup_summary["bounces_detected"]
    summary["finished_at"] = _now().isoformat()

    if not args.dry_run:
        state.append_run(summary)
        state.save()

    if discovery.apollo_error:
        logger.error("%s", discovery.apollo_error)
    if new_send_error:
        logger.error("%s", new_send_error)
    print_summary(summary)
    return 1 if discovery.apollo_error or new_send_error else 0


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    if args.mode == "daily":
        return run_daily(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
