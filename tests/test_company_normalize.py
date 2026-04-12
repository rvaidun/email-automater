"""Tests for company normalization helpers."""

from utils.company_normalize import clean_company_display_name, normalize_company_name


def test_normalize_company_name_strips_suffixes_and_punctuation():
    """Company keys should be lowercase, punctuation-light, and suffix-safe."""
    assert normalize_company_name("Stripe, Inc.") == "stripe"
    assert normalize_company_name("Acme   LLC") == "acme"
    assert normalize_company_name("Northrop-Grumman Corporation") == "northrop grumman"


def test_clean_company_display_name_collapses_spacing():
    """Display names should keep readable casing while trimming whitespace."""
    assert clean_company_display_name("  Leidos   ") == "Leidos"
