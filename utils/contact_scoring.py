"""Recruiter contact scoring helpers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

TARGET_TITLES = [
    "recruiter",
    "technical recruiter",
    "university recruiter",
    "campus recruiter",
    "early career recruiter",
    "talent acquisition",
    "talent partner",
    "recruiting coordinator",
    "university programs recruiter",
]

FALLBACK_TITLES = [
    "engineering recruiting",
    "early career programs",
    "university programs",
]

BROAD_FALLBACK_TITLES = [
    "talent acquisition specialist",
    "talent acquisition coordinator",
    "recruiting operations",
    "recruiting ops",
    "recruiting assistant",
    "people operations",
    "people ops",
    "people partner",
    "human resources",
    "sourcer",
    "staffing",
]

REJECTED_TITLE_KEYWORDS = [
    "founder",
    "chief",
    "ceo",
    "cto",
    "cfo",
    "president",
    "vp",
    "vice president",
    "engineer",
    "developer",
    "sales",
    "product",
    "finance",
]

ALLOWED_HR_HINTS = [
    "recruit",
    "talent",
    "university",
    "campus",
    "early career",
    "people",
    "operations",
    "ops",
    "sourc",
    "staff",
]


def _title(value: str | None) -> str:
    return (value or "").strip().lower()


def is_rejected_title(title: str | None) -> bool:
    """Return True when a title should be skipped by default."""
    lowered = _title(title)
    if any(keyword in lowered for keyword in REJECTED_TITLE_KEYWORDS):
        return not any(hint in lowered for hint in ALLOWED_HR_HINTS)
    return False


def title_priority(title: str | None) -> int:
    """Return the priority bucket for a job title."""
    lowered = _title(title)
    for index, target in enumerate(TARGET_TITLES):
        if target in lowered:
            return 100 - index
    for index, target in enumerate(FALLBACK_TITLES):
        if target in lowered:
            return 40 - index
    for index, target in enumerate(BROAD_FALLBACK_TITLES):
        if target in lowered:
            return 20 - index
    if "hr" in lowered and any(hint in lowered for hint in ALLOWED_HR_HINTS):
        return 15
    return -100


def score_contact(contact: Mapping[str, object]) -> int:  # noqa: C901
    """Score a recruiter candidate. Higher is better."""
    title = _title(str(contact.get("title", "")))
    if is_rejected_title(title):
        return -10_000

    score = title_priority(title)
    if score < 0:
        return score

    email = str(contact.get("email", "")).strip()
    email_status = _title(str(contact.get("email_status", "")))

    if email:
        score += 35
    if email_status == "verified":
        score += 25
    elif email_status == "likely to engage":
        score += 20
    elif email_status == "unverified":
        score += 10

    seniority = _title(str(contact.get("seniority", "")))
    if seniority in {"manager", "director"}:
        score += 5
    if seniority in {"owner", "founder", "c_suite", "vp", "head"}:
        score -= 50

    headline = _title(str(contact.get("headline", "")))
    if any(keyword in headline for keyword in ("new grad", "early career", "campus")):
        score += 10

    refreshed = str(contact.get("last_refreshed_at", "")).strip()
    if refreshed:
        try:
            datetime.fromisoformat(refreshed)
        except ValueError:
            pass
        else:
            score += 3

    return score


def select_best_contacts(
    contacts: Iterable[Mapping[str, object]],
    *,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Return the highest scoring recruiter contacts."""
    scored_contacts: list[tuple[int, dict[str, object]]] = []
    for contact in contacts:
        materialized = dict(contact)
        score = score_contact(materialized)
        if score < 0:
            continue
        materialized["score"] = score
        scored_contacts.append((score, materialized))

    scored_contacts.sort(
        key=lambda item: (
            item[0],
            str(item[1].get("email_status", "")) == "verified",
            bool(item[1].get("email")),
        ),
        reverse=True,
    )
    return [contact for _, contact in scored_contacts[:limit]]
