"""Apollo API client for recruiter discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

import requests
from dotenv import load_dotenv

from utils.company_normalize import company_key
from utils.contact_scoring import (
    BROAD_FALLBACK_TITLES,
    FALLBACK_TITLES,
    TARGET_TITLES,
    select_best_contacts,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

load_dotenv()

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
APOLLO_RATE_LIMIT_STATUS = 429
DEFAULT_REQUEST_BUDGET = 60
DEFAULT_MATCH_CALL_LIMIT_PER_COMPANY = 3


class ApolloError(RuntimeError):
    """Raised when Apollo returns an error response."""


class ApolloQuotaError(ApolloError):
    """Raised when Apollo credits or rate limits prevent more discovery."""


@dataclass(slots=True)
class ApolloOrganization:
    """Minimal organization payload used by the pipeline."""

    id: str
    name: str
    domain: str | None
    website_url: str | None


class ApolloClient:
    """Thin Apollo client built around the endpoints in the spec."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: int = 20,
        request_budget: int | None = None,
        match_call_limit_per_company: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize the Apollo client."""
        self.api_key = api_key or os.getenv("APOLLO_API_KEY")
        if not self.api_key:
            msg = "Missing APOLLO_API_KEY"
            raise ValueError(msg)
        self.timeout = timeout
        raw_budget = (
            request_budget
            if request_budget is not None
            else int(os.getenv("APOLLO_REQUEST_BUDGET_PER_RUN", DEFAULT_REQUEST_BUDGET))
        )
        self.request_budget = max(raw_budget, 0)
        raw_match_limit = (
            match_call_limit_per_company
            if match_call_limit_per_company is not None
            else int(
                os.getenv(
                    "APOLLO_MATCH_CALL_LIMIT_PER_COMPANY",
                    DEFAULT_MATCH_CALL_LIMIT_PER_COMPANY,
                )
            )
        )
        self.match_call_limit_per_company = max(raw_match_limit, 0)
        self.requests_made = 0
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "accept": "application/json",
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key,
            }
        )

    def _request(
        self,
        path: str,
        *,
        params: list[tuple[str, Any]] | dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.requests_made >= self.request_budget:
            msg = (
                "Apollo per-run request budget reached before "
                f"{path} ({self.requests_made}/{self.request_budget})"
            )
            raise ApolloQuotaError(msg)
        self.requests_made += 1
        response = self.session.post(
            f"{APOLLO_BASE_URL}{path}",
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        if not response.ok:
            response_text = response.text[:500]
            msg = (
                f"Apollo request failed for {path}: "
                f"{response.status_code} {response_text}"
            )
            lowered_text = response_text.lower()
            if response.status_code == APOLLO_RATE_LIMIT_STATUS or any(
                marker in lowered_text
                for marker in (
                    "insufficient credits",
                    "lead credits",
                    "maximum number of api calls",
                )
            ):
                raise ApolloQuotaError(msg)
            raise ApolloError(msg)
        return response.json()

    def search_organization(self, company_name: str) -> ApolloOrganization | None:
        """Find the best matching Apollo organization for a company name."""
        payload = self._request(
            "/mixed_companies/search",
            params={"q_organization_name": company_name, "page": 1, "per_page": 5},
        )
        organizations = payload.get("organizations", [])
        if not isinstance(organizations, list) or not organizations:
            return None

        ranked = sorted(
            organizations,
            key=lambda org: self.organization_match_score(company_name, org),
            reverse=True,
        )
        match = ranked[0]
        if self.organization_match_score(company_name, match) <= 0:
            return None
        return ApolloOrganization(
            id=str(match["id"]),
            name=str(match.get("name", company_name)),
            domain=(
                str(match.get("primary_domain"))
                if match.get("primary_domain")
                else None
            ),
            website_url=(
                str(match.get("website_url")) if match.get("website_url") else None
            ),
        )

    @staticmethod
    def organization_match_score(
        requested_name: str,
        organization: dict[str, Any],
    ) -> float:
        """Score how closely an Apollo organization matches the requested company."""
        requested_key = company_key(requested_name)
        candidate_key = company_key(str(organization.get("name", "")))
        if not requested_key or not candidate_key:
            return -1.0

        requested_tokens = requested_key.split()
        candidate_tokens = candidate_key.split()
        overlap = len(set(requested_tokens) & set(candidate_tokens))
        score = overlap * 20.0

        if candidate_key == requested_key:
            score += 500.0
        if candidate_tokens[: len(requested_tokens)] == requested_tokens:
            score += 250.0
        if requested_key in candidate_key:
            score += 125.0
        if all(token in candidate_tokens for token in requested_tokens):
            score += 100.0

        score += SequenceMatcher(None, requested_key, candidate_key).ratio() * 100.0
        score -= max(len(candidate_tokens) - len(requested_tokens), 0) * 8.0
        if organization.get("primary_domain"):
            score += 2.0
        return score

    def search_people(
        self,
        organization: ApolloOrganization,
        *,
        titles: Iterable[str] | None = None,
        per_page: int = 15,
    ) -> list[dict[str, Any]]:
        """Search recruiter-like people at an organization."""
        title_values = list(titles or [*TARGET_TITLES, *FALLBACK_TITLES])
        params: list[tuple[str, Any]] = [
            ("organization_ids[]", organization.id),
            ("include_similar_titles", "true"),
            ("page", 1),
            ("per_page", per_page),
        ]
        params.extend(("person_titles[]", title) for title in title_values)
        params.extend(
            ("contact_email_status[]", status)
            for status in ("verified", "likely to engage", "unverified")
        )

        payload = self._request("/mixed_people/api_search", params=params)
        people = payload.get("people", [])
        return [dict(person) for person in people] if isinstance(people, list) else []

    def enrich_person(self, person_id: str) -> dict[str, Any] | None:
        """Reveal the contact email for a single person."""
        payload = self._request(
            "/people/match",
            json_body={
                "id": person_id,
                "reveal_personal_emails": False,
                "reveal_phone_number": False,
            },
        )
        person = payload.get("person")
        return dict(person) if isinstance(person, dict) else None

    def find_recruiter_contacts(
        self,
        company_name: str,
        *,
        limit: int = 3,
    ) -> tuple[ApolloOrganization | None, list[dict[str, Any]]]:
        """Return enriched recruiter contacts for a company."""
        organization = self.search_organization(company_name)
        if organization is None:
            return None, []

        search_results = self.search_people(
            organization,
            titles=[*TARGET_TITLES, *FALLBACK_TITLES],
            per_page=max(limit * 5, 15),
        )
        candidate_pool = select_best_contacts(search_results, limit=max(limit * 4, 12))
        if len(candidate_pool) < limit:
            broader_results = self.search_people(
                organization,
                titles=BROAD_FALLBACK_TITLES,
                per_page=max(limit * 5, 15),
            )
            deduped_candidates: dict[str, dict[str, Any]] = {}
            for candidate in [*search_results, *broader_results]:
                candidate_id = str(candidate.get("id", "")).strip()
                fallback_key = str(candidate.get("email", "")).strip().lower()
                dedupe_key = candidate_id or fallback_key
                if not dedupe_key:
                    continue
                deduped_candidates.setdefault(dedupe_key, dict(candidate))
            candidate_pool = select_best_contacts(
                deduped_candidates.values(),
                limit=max(limit * 4, 12),
            )
        max_match_calls = min(self.match_call_limit_per_company, len(candidate_pool))

        enriched_contacts: list[dict[str, Any]] = []
        seen_emails: set[str] = set()
        for candidate in candidate_pool[:max_match_calls]:
            person_id = str(candidate.get("id", "")).strip()
            if not person_id:
                continue
            enriched = self.enrich_person(person_id)
            if not enriched:
                continue

            email = str(enriched.get("email", "")).strip().lower()
            if not email or email in seen_emails:
                continue

            contact = {
                "apollo_id": str(enriched.get("id", person_id)),
                "name": str(enriched.get("name", "")).strip()
                or " ".join(
                    part
                    for part in [
                        str(enriched.get("first_name", "")).strip(),
                        str(enriched.get("last_name", "")).strip(),
                    ]
                    if part
                ),
                "title": str(enriched.get("title", candidate.get("title", ""))).strip(),
                "headline": str(
                    enriched.get("headline", candidate.get("headline", ""))
                ).strip(),
                "email": email,
                "email_status": str(enriched.get("email_status", "")).strip().lower(),
                "seniority": str(enriched.get("seniority", "")).strip().lower(),
                "linkedin_url": str(enriched.get("linkedin_url", "")).strip() or None,
                "organization_id": str(
                    enriched.get("organization_id", organization.id)
                ).strip(),
                "organization_name": organization.name,
            }
            seen_emails.add(email)
            enriched_contacts.append(contact)
            if len(enriched_contacts) >= limit:
                break

        return organization, select_best_contacts(enriched_contacts, limit=limit)
