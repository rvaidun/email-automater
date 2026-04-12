"""Tests for Apollo organization matching heuristics."""

from utils.apollo import ApolloClient


def test_organization_match_prefers_exact_company_over_lookalike_domain():
    """The scorer should prefer the real org over lookalike training pages."""
    actual = {
        "name": "Amazon Web Services (AWS)",
        "primary_domain": None,
    }
    lookalike = {
        "name": "Amazon Web Services Online Training",
        "primary_domain": "orbittrainings.com",
    }

    actual_score = ApolloClient.organization_match_score(
        "Amazon Web Services",
        actual,
    )
    lookalike_score = ApolloClient.organization_match_score(
        "Amazon Web Services",
        lookalike,
    )

    assert actual_score > lookalike_score


def test_organization_match_prefers_exact_lab_name_over_security():
    """The scorer should prefer the exact Lawrence Livermore lab name."""
    laboratory = {
        "name": "Lawrence Livermore National Laboratory",
        "primary_domain": "llnl.gov",
    }
    security = {
        "name": "Lawrence Livermore National Security",
        "primary_domain": "llnsllc.com",
    }

    laboratory_score = ApolloClient.organization_match_score(
        "Lawrence Livermore National Laboratory",
        laboratory,
    )
    security_score = ApolloClient.organization_match_score(
        "Lawrence Livermore National Laboratory",
        security,
    )

    assert laboratory_score > security_score
