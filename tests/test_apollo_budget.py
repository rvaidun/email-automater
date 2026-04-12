"""Tests for Apollo request budgeting."""

from types import SimpleNamespace

import pytest

from utils.apollo import ApolloClient, ApolloQuotaError


class _FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def post(self, *_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(ok=True, json=lambda: {"organizations": []})


def test_apollo_client_stops_when_request_budget_is_exhausted():
    """Apollo client should stop before making requests past the local budget."""
    client = ApolloClient(
        api_key="test-key",
        request_budget=0,
        session=_FakeSession(),
    )

    with pytest.raises(ApolloQuotaError):
        client.search_organization("Stripe")


def test_apollo_client_caps_match_calls_per_company():
    """Recruiter enrichment should stop at the configured per-company match cap."""
    client = ApolloClient(
        api_key="test-key",
        request_budget=50,
        match_call_limit_per_company=2,
        session=_FakeSession(),
    )
    client.search_organization = lambda *_: SimpleNamespace(  # type: ignore[method-assign]
        id="org-1",
        name="Stripe",
        domain="stripe.com",
        website_url="https://stripe.com",
    )
    client.search_people = lambda *_, **__: [  # type: ignore[method-assign]
        {"id": "1", "name": "A", "title": "Recruiter"},
        {"id": "2", "name": "B", "title": "Recruiter"},
        {"id": "3", "name": "C", "title": "Recruiter"},
    ]
    seen: list[str] = []

    def fake_enrich(person_id: str) -> dict[str, str]:
        seen.append(person_id)
        return {
            "id": person_id,
            "name": f"Recruiter {person_id}",
            "title": "Recruiter",
            "email": f"{person_id}@stripe.com",
            "organization_id": "org-1",
        }

    client.enrich_person = fake_enrich  # type: ignore[method-assign]

    _, contacts = client.find_recruiter_contacts("Stripe", limit=7)

    assert len(contacts) == 2
    assert seen == ["1", "2"]


def test_apollo_client_falls_back_to_broader_hr_titles():
    """Broader HR/talent searches should backfill when recruiters are sparse."""
    client = ApolloClient(
        api_key="test-key",
        request_budget=50,
        match_call_limit_per_company=3,
        session=_FakeSession(),
    )
    client.search_organization = lambda *_: SimpleNamespace(  # type: ignore[method-assign]
        id="org-1",
        name="Stripe",
        domain="stripe.com",
        website_url="https://stripe.com",
    )
    seen_title_batches: list[list[str]] = []

    def fake_search_people(*_, titles=None, **__):
        seen_title_batches.append(list(titles or []))
        if len(seen_title_batches) == 1:
            return [{"id": "1", "name": "Recruiter A", "title": "Recruiter"}]
        return [
            {
                "id": "2",
                "name": "People Ops A",
                "title": "People Operations",
            },
            {
                "id": "3",
                "name": "Talent Specialist A",
                "title": "Talent Acquisition Specialist",
            },
        ]

    client.search_people = fake_search_people  # type: ignore[method-assign]
    client.enrich_person = lambda person_id: {  # type: ignore[method-assign]
        "id": person_id,
        "name": f"Recruiter {person_id}",
        "title": "Recruiter",
        "email": f"{person_id}@stripe.com",
        "organization_id": "org-1",
    }

    _, contacts = client.find_recruiter_contacts("Stripe", limit=3)

    assert len(seen_title_batches) == 2
    assert len(contacts) == 3
