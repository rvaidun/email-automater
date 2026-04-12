"""Helpers for normalizing company names."""

from __future__ import annotations

import re

CORPORATE_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
}

WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_RE = re.compile(r"[^\w\s]")


def clean_company_display_name(name: str) -> str:
    """Return a display-safe company name."""
    cleaned = WHITESPACE_RE.sub(" ", name.strip())
    return cleaned.strip(" ,.-")


def normalize_company_name(name: str) -> str:
    """Return the canonical lookup key for a company."""
    lowered = clean_company_display_name(name).lower().replace("&", " and ")
    lowered = PUNCTUATION_RE.sub(" ", lowered)
    parts = [part for part in WHITESPACE_RE.sub(" ", lowered).split(" ") if part]

    while parts and parts[-1] in CORPORATE_SUFFIXES and len(parts) > 1:
        parts.pop()

    return " ".join(parts)


def company_key(name: str) -> str:
    """Alias for the canonical company key used across the pipeline."""
    return normalize_company_name(name)
