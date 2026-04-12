"""Helpers for recruiter-facing name formatting."""

from __future__ import annotations

import re

SALUTATION_PREFIXES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
}

WHITESPACE_RE = re.compile(r"\s+")


def recruiter_first_name(full_name: str) -> str:
    """Return a recruiter's first name for greeting/subject use."""
    cleaned = WHITESPACE_RE.sub(" ", full_name.strip())
    if not cleaned:
        return "there"

    for token in cleaned.split(" "):
        stripped = token.strip(" ,.-")
        if not stripped:
            continue
        if stripped.lower().rstrip(".") in SALUTATION_PREFIXES:
            continue
        return stripped
    return cleaned.split(" ", 1)[0]


def recruiter_template_context(
    *,
    recruiter_company: str,
    recruiter_name: str,
) -> dict[str, str]:
    """Return template placeholders used by subjects/bodies/follow-ups."""
    first_name = recruiter_first_name(recruiter_name)
    return {
        "company": recruiter_company,
        "recruiter_company": recruiter_company,
        "recruiter_name": first_name,
        "recruiter_first_name": first_name,
        "recruiterfirstname": first_name,
        "recruiter_full_name": recruiter_name,
    }
