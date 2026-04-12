"""Stateful helpers used by the daily pipeline orchestrator."""

# ruff: noqa: PLR0913

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from utils.apollo import ApolloError, ApolloQuotaError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from logging import Logger
    from pathlib import Path

    from utils.apollo import ApolloClient
    from utils.outreach_state import OutreachStateStore


@dataclass(slots=True)
class RunPlan:
    """Precomputed run decisions used by the daily pipeline."""

    remaining_capacity: int
    can_queue_new_outreach: bool
    should_run_apollo: bool


@dataclass(slots=True)
class DiscoveryPhase:
    """Result of the scrape and contact-discovery phase."""

    companies: list[Any]
    contacts: list[dict[str, Any]]
    scraped_count: int
    skipped_count: int
    contacts_found: int
    duplicates: int
    apollo_error: str | None


def build_run_plan(
    *,
    requested_limit: int,
    daily_outreach_limit: int,
    already_actioned_today: int,
    is_outreach_day: bool,
    can_queue_new_outreach: bool,
) -> RunPlan:
    """Compute high-level run decisions before discovery starts."""
    remaining_capacity = max(
        min(requested_limit, daily_outreach_limit) - already_actioned_today,
        0,
    )
    return RunPlan(
        remaining_capacity=remaining_capacity,
        can_queue_new_outreach=can_queue_new_outreach,
        should_run_apollo=(
            is_outreach_day and remaining_capacity > 0 and can_queue_new_outreach
        ),
    )


def select_companies(
    *,
    state: OutreachStateStore,
    now: datetime,
    screenshot: Path | None,
    scrape_companies: Callable[..., list[Any]],
    title_matches: Callable[[str], bool],
    title_priority: Callable[[str], int],
    max_companies_per_run: int,
) -> tuple[list[Any], int, int]:
    """Scrape, record, filter, and prioritize candidate companies."""
    companies = scrape_companies(screenshot=screenshot, now=now)
    unique_companies: dict[str, Any] = {}
    skipped = 0
    for company in companies:
        state.mark_company_seen(
            company.display_name,
            source=company.source,
            seen_at=now,
        )
        allowed, reason = state.can_contact_company(company.company_key, now=now)
        if not allowed:
            if reason in {"cooldown", "daily_limit", "sixty_day_limit"}:
                skipped += 1
            continue
        if not title_matches(company.job_title):
            continue
        unique_companies.setdefault(company.company_key, company)
    prioritized = sorted(
        unique_companies.values(),
        key=lambda company: (
            title_priority(company.job_title),
            company.posted_at,
            company.display_name,
        ),
        reverse=True,
    )
    return prioritized[:max_companies_per_run], skipped, len(companies)


def discover_contacts(
    *,
    companies: list[Any],
    state: OutreachStateStore,
    apollo_client: ApolloClient,
    limit: int,
    per_company_limit: int,
    find_contacts_for_company: Callable[..., dict[str, Any]],
    logger: Logger,
) -> tuple[list[dict[str, Any]], int, int, str | None]:
    """Discover recruiter contacts while preserving the existing stop rules."""
    selected: list[dict[str, Any]] = []
    contacts_found = 0
    duplicates = 0
    quota_error: str | None = None

    for company in companies:
        try:
            result = find_contacts_for_company(
                company.display_name,
                apollo_client=apollo_client,
                state=state,
                limit=per_company_limit,
            )
        except ApolloQuotaError as exc:
            quota_error = str(exc)
            logger.warning(
                "Apollo quota/rate limit reached; stopping recruiter discovery: %s",
                exc,
            )
            break
        except ApolloError as exc:
            logger.warning("Apollo error for %s: %s", company.display_name, exc)
            continue

        contacts = result["contacts"]
        contacts_found += len(contacts)
        duplicates += int(result["duplicates_skipped"])
        if not contacts:
            continue

        for contact in contacts:
            selected_contact = dict(contact)
            selected_contact["company_display_name"] = company.display_name
            selected_contact["company_key"] = company.company_key
            selected.append(selected_contact)
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break

    return selected, contacts_found, duplicates, quota_error


def run_discovery_phase(
    *,
    plan: RunPlan,
    state: OutreachStateStore,
    now: datetime,
    screenshot: Path | None,
    scrape_companies: Callable[..., list[Any]],
    title_matches: Callable[[str], bool],
    title_priority: Callable[[str], int],
    max_companies_per_run: int,
    dry_run: bool,
    allow_paid_apollo_in_dry_run: bool,
    is_outreach_day: bool,
    apollo_api_key: str | None,
    apollo_client_factory: Callable[..., ApolloClient],
    find_contacts_for_company: Callable[..., dict[str, Any]],
    per_company_limit: int,
    logger: Logger,
) -> DiscoveryPhase:
    """Run scrape + contact discovery and return a structured result."""
    companies, skipped, scraped_count = select_companies(
        state=state,
        now=now,
        screenshot=screenshot,
        scrape_companies=scrape_companies,
        title_matches=title_matches,
        title_priority=title_priority,
        max_companies_per_run=max_companies_per_run,
    )

    contacts: list[dict[str, Any]] = []
    contacts_found = 0
    duplicates = 0
    apollo_error: str | None = None

    if (
        is_outreach_day
        and plan.remaining_capacity > 0
        and not plan.can_queue_new_outreach
    ):
        logger.info(
            "Skipping Apollo discovery because new outreach cannot be sent safely "
            "outside the current send window."
        )
    if dry_run and plan.should_run_apollo and not allow_paid_apollo_in_dry_run:
        logger.info(
            "Dry run: skipping Apollo discovery to avoid spending paid credits. "
            "Re-run with --allow-paid-apollo-in-dry-run to opt in."
        )
    if plan.should_run_apollo and (not dry_run or allow_paid_apollo_in_dry_run):
        try:
            apollo_client = apollo_client_factory(api_key=apollo_api_key)
        except ValueError as exc:
            apollo_error = str(exc)
        else:
            contacts, contacts_found, duplicates, quota_error = discover_contacts(
                companies=companies,
                state=state,
                apollo_client=apollo_client,
                limit=plan.remaining_capacity,
                per_company_limit=per_company_limit,
                find_contacts_for_company=find_contacts_for_company,
                logger=logger,
            )
            if quota_error:
                apollo_error = quota_error

    return DiscoveryPhase(
        companies=companies,
        contacts=contacts,
        scraped_count=scraped_count,
        skipped_count=skipped,
        contacts_found=contacts_found,
        duplicates=duplicates,
        apollo_error=apollo_error,
    )
