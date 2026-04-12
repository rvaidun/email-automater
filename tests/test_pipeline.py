"""Tests for the daily pipeline orchestration."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pipeline
from tests.pipeline_helpers import (
    make_daily_args,
    make_followup_summary,
    make_scraped_company,
    make_single_company_scraper,
)
from utils import outreach_delivery
from utils.outreach_state import OutreachStateStore


def test_run_daily_dry_run_prints_required_summary(monkeypatch, tmp_path, capsys):
    """Dry runs should print the required summary fields without sending."""
    now = datetime(2026, 4, 10, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    def fake_apollo_client(**_: object) -> object:
        return object()

    def fake_find_contacts_for_company(
        company_name: str,
        *,
        apollo_client: object,
        state: object,
        limit: int,
    ) -> dict[str, object]:
        del apollo_client, state, limit
        return {
            "company": company_name,
            "organization": {"id": "org-1"},
            "contacts": [
                {
                    "name": "Jane Doe",
                    "title": "Technical Recruiter",
                    "email": "jane@stripe.com",
                }
            ],
            "duplicates_skipped": 0,
        }

    def fake_process_followups(**_: object) -> dict[str, int]:
        return make_followup_summary(followups_sent=1, replies_detected=1)

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(pipeline, "ApolloClient", fake_apollo_client)
    monkeypatch.setattr(
        pipeline,
        "find_contacts_for_company",
        fake_find_contacts_for_company,
    )
    monkeypatch.setattr(pipeline, "process_followups", fake_process_followups)

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=True,
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "companies scraped: 1" in captured
    assert "new emails queued/sent: 1" in captured
    assert "follow-ups sent: 1" in captured


def test_run_daily_dry_run_skips_paid_apollo_by_default(
    monkeypatch,
    tmp_path,
    capsys,
):
    """Dry runs should not spend Apollo credits unless explicitly opted in."""
    now = datetime(2026, 4, 10, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "ApolloClient",
        lambda **_: (_ for _ in ()).throw(AssertionError("Apollo should not run")),
    )
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=False,
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "companies scraped: 1" in captured
    assert "contacts found: 0" in captured
    assert "new emails queued/sent: 0" in captured


def test_run_daily_respects_true_daily_cap(monkeypatch, tmp_path, capsys):
    """A second run the same day should not exceed the daily outreach cap."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    store.mark_contact_sent(
        email="existing@stripe.com",
        company_name="Stripe",
        name="Existing Recruiter",
        title="Technical Recruiter",
        thread_id="thread-existing",
        source="apollo",
        sent_at=now,
        actioned_at=now,
    )
    store.save()

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=False,
        limit=1,
        state_path=state_path,
        token_name="gmail-token.json",
        creds_name="gmail-credentials.json",
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "new emails queued/sent: 0" in captured


def test_run_daily_uses_conservative_default_daily_limit(monkeypatch, tmp_path, capsys):
    """Default daily new-outreach volume should stay conservative."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))

    monkeypatch.delenv("NEW_OUTREACH_DAILY_LIMIT", raising=False)
    monkeypatch.delenv("MAX_COMPANIES_PER_RUN", raising=False)
    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setattr(
        pipeline,
        "scrape_companies",
        lambda **_: [
            make_scraped_company(
                now,
                display_name=f"Company {index}",
                company_key=f"company {index}",
                listing_url=f"https://example.com/job/{index}",
            )
            for index in range(20)
        ],
    )
    monkeypatch.setattr(pipeline, "ApolloClient", lambda **_: object())
    monkeypatch.setattr(
        pipeline,
        "find_contacts_for_company",
        lambda company_name, **_: {
            "company": company_name,
            "organization": {"id": f"org-{company_name}"},
            "contacts": [
                {
                    "name": "Jane Doe",
                    "title": "Technical Recruiter",
                    "email": f"{company_name.replace(' ', '').lower()}@example.com",
                }
            ],
            "duplicates_skipped": 0,
        },
    )
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=True,
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "new emails queued/sent: 15" in captured


def test_select_companies_filters_non_software_titles(tmp_path):
    """Only software/cloud-ish titles should pass the pipeline filter."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    expected_scraped_count = 2

    original_scrape = pipeline.scrape_companies
    pipeline.scrape_companies = lambda **_: [  # type: ignore[assignment]
        make_scraped_company(
            now,
            display_name="Stripe",
            listing_url="https://example.com/stripe",
        ),
        make_scraped_company(
            now,
            display_name="Volga Partners",
            company_key="volga partners",
            job_title="AI Writing Evaluators",
            listing_url="https://example.com/volga",
        ),
    ]
    try:
        companies, skipped, scraped_count = pipeline._select_companies(  # noqa: SLF001
            state=state,
            now=now,
            screenshot=None,
        )
    finally:
        pipeline.scrape_companies = original_scrape  # type: ignore[assignment]

    assert scraped_count == expected_scraped_count
    assert skipped == 0
    assert [company.display_name for company in companies] == ["Stripe"]


def test_discover_contacts_uses_cost_effective_default_limit(monkeypatch, tmp_path):
    """Daily discovery should only enrich one recruiter per company by default."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    seen_limits: list[int] = []

    monkeypatch.delenv(
        "PIPELINE_CONTACT_DISCOVERY_LIMIT_PER_COMPANY",
        raising=False,
    )

    def fake_find_contacts_for_company(
        company_name: str,
        *,
        apollo_client: object,
        state: object,
        limit: int,
    ) -> dict[str, object]:
        del apollo_client, state
        seen_limits.append(limit)
        return {
            "company": company_name,
            "organization": {"id": "org-1"},
            "contacts": [
                {
                    "name": "Jane Doe",
                    "title": "Technical Recruiter",
                    "email": "jane@stripe.com",
                }
            ],
            "duplicates_skipped": 0,
        }

    monkeypatch.setattr(
        pipeline,
        "find_contacts_for_company",
        fake_find_contacts_for_company,
    )

    selected, contacts_found, duplicates, quota_error = pipeline._discover_contacts(  # noqa: SLF001
        companies=[make_scraped_company(now)],
        state=state,
        apollo_client=object(),
        limit=1,
    )

    assert seen_limits == [1]
    assert len(selected) == 1
    assert contacts_found == 1
    assert duplicates == 0
    assert quota_error is None


def test_discover_contacts_keeps_multiple_contacts_per_company(monkeypatch, tmp_path):
    """The pipeline should keep multiple recruiters from the same company."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    monkeypatch.setenv("PIPELINE_CONTACT_DISCOVERY_LIMIT_PER_COMPANY", "3")

    monkeypatch.setattr(
        pipeline,
        "find_contacts_for_company",
        lambda *_, **__: {
            "company": "Stripe",
            "organization": {"id": "org-1"},
            "contacts": [
                {"name": "A", "title": "Recruiter", "email": "a@stripe.com"},
                {"name": "B", "title": "Recruiter", "email": "b@stripe.com"},
                {"name": "C", "title": "Recruiter", "email": "c@stripe.com"},
            ],
            "duplicates_skipped": 0,
        },
    )

    contacts, contacts_found, duplicates, quota_error = pipeline._discover_contacts(  # noqa: SLF001
        companies=[make_scraped_company(now)],
        state=state,
        apollo_client=object(),
        limit=10,
    )

    assert quota_error is None
    assert contacts_found == 3
    assert duplicates == 0
    assert [contact["email"] for contact in contacts] == [
        "a@stripe.com",
        "b@stripe.com",
        "c@stripe.com",
    ]


def test_select_companies_prioritizes_software_titles(tmp_path):
    """Software titles should rank ahead of broader cloud/platform matches."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")

    original_scrape = pipeline.scrape_companies
    pipeline.scrape_companies = lambda **_: [  # type: ignore[assignment]
        make_scraped_company(
            now,
            display_name="Cloud Co",
            company_key="cloud co",
            job_title="Cloud Engineer",
            listing_url="https://example.com/cloud",
        ),
        make_scraped_company(
            now,
            display_name="Software Co",
            company_key="software co",
            listing_url="https://example.com/software",
        ),
    ]
    try:
        companies, skipped, scraped_count = pipeline._select_companies(  # noqa: SLF001
            state=state,
            now=now,
            screenshot=None,
        )
    finally:
        pipeline.scrape_companies = original_scrape  # type: ignore[assignment]

    assert scraped_count == 2
    assert skipped == 0
    assert [company.display_name for company in companies] == [
        "Software Co",
        "Cloud Co",
    ]


def test_select_companies_honors_company_cap(monkeypatch, tmp_path):
    """Only the configured number of companies should be passed into Apollo."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    monkeypatch.setenv("MAX_COMPANIES_PER_RUN", "2")

    original_scrape = pipeline.scrape_companies
    pipeline.scrape_companies = lambda **_: [  # type: ignore[assignment]
        make_scraped_company(
            now,
            display_name=f"Company {index}",
            company_key=f"company {index}",
            listing_url=f"https://example.com/{index}",
        )
        for index in range(4)
    ]
    try:
        companies, skipped, scraped_count = pipeline._select_companies(  # noqa: SLF001
            state=state,
            now=now,
            screenshot=None,
        )
    finally:
        pipeline.scrape_companies = original_scrape  # type: ignore[assignment]

    assert scraped_count == 4
    assert skipped == 0
    assert len(companies) == 2


def test_outreach_day_can_include_sunday(monkeypatch):
    """Sunday outreach should be allowed when configured in env."""
    sunday = datetime(2026, 4, 12, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    monkeypatch.setenv("OUTREACH_WEEKDAYS", "0,1,2,3,4,6")

    assert pipeline._is_outreach_day(sunday) is True  # noqa: SLF001


def test_run_daily_skips_apollo_when_sunday_is_after_hours(
    monkeypatch,
    tmp_path,
    capsys,
):
    """After-hours Sunday runs should not spend Apollo."""
    now = datetime(2026, 4, 12, 19, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setenv("OUTREACH_WEEKDAYS", "0,1,2,3,4,6")
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "ApolloClient",
        lambda **_: (_ for _ in ()).throw(AssertionError("Apollo should not run")),
    )
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=False,
        allow_paid_apollo_in_dry_run=False,
        state_path=state_path,
        token_path="token.json",
        creds_path="credentials.json",
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "contacts found: 0" in captured
    assert "new emails queued/sent: 0" in captured


def test_queue_new_outreach_sends_immediately_inside_send_window(monkeypatch, tmp_path):
    """Inside the send window, outreach should send immediately with local pacing."""
    now = datetime(2026, 4, 10, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    sent_messages: list[tuple[str, str]] = []

    class FakeGmail:
        def send_now(self, message: object) -> dict[str, str]:
            sent_messages.append(
                (
                    str(message["To"]),
                    str(message["Subject"]),
                )
            )
            return {"threadId": "thread-1"}

    monkeypatch.setenv("TIMEZONE", "America/Los_Angeles")
    monkeypatch.delenv("EMAIL_SUBJECT", raising=False)
    monkeypatch.setattr(pipeline, "_sleep_until", lambda *_: None)
    monkeypatch.setattr(
        outreach_delivery,
        "load_authenticated_gmail",
        lambda **_: (FakeGmail(), object()),
    )

    fake_token_path = str(tmp_path / "gmail-token.json")
    fake_creds_path = str(tmp_path / "gmail-credentials.json")
    queued, error = pipeline._queue_new_outreach(  # noqa: SLF001
        contacts=[
            {
                "company_display_name": "Stripe",
                "name": "Jane Doe",
                "title": "Technical Recruiter",
                "email": "jane@stripe.com",
            }
        ],
        state=state,
        now=now,
        token_path=fake_token_path,
        creds_path=fake_creds_path,
        dry_run=False,
    )

    assert error is None
    assert queued == 1
    assert sent_messages == [("jane@stripe.com", "Software Engineer - Stripe")]


def test_run_daily_skips_apollo_on_weekends(monkeypatch, tmp_path, capsys):
    """Weekend runs should not spend Apollo requests on new-outreach discovery."""
    now = datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    state_path = tmp_path / "outreach_state.json"

    monkeypatch.setattr(pipeline, "_now", lambda: now)
    monkeypatch.setenv("OUTREACH_WEEKDAYS", "0,1,2,3,4")
    monkeypatch.setattr(pipeline, "scrape_companies", make_single_company_scraper(now))
    monkeypatch.setattr(
        pipeline,
        "ApolloClient",
        lambda **_: (_ for _ in ()).throw(AssertionError("Apollo should not run")),
    )
    monkeypatch.setattr(
        pipeline,
        "process_followups",
        lambda **_: make_followup_summary(),
    )

    args = make_daily_args(
        tmp_path,
        dry_run=True,
        allow_paid_apollo_in_dry_run=False,
        state_path=state_path,
        token_path="fake-token.json",
        creds_path="fake-credentials.json",
    )

    result = pipeline.run_daily(args)

    captured = capsys.readouterr().out
    assert result == 0
    assert "companies scraped: 1" in captured
    assert "contacts found: 0" in captured
    assert "new emails queued/sent: 0" in captured


def test_render_initial_email_uses_email1_subject_and_first_name(monkeypatch):
    """Initial outreach should use email1's inline subject and first-name greeting."""
    monkeypatch.delenv("EMAIL_SUBJECT", raising=False)
    monkeypatch.setenv("MESSAGE_BODY_PATH", "email1.md")

    subject, message = pipeline._render_initial_email(  # noqa: SLF001
        recruiter_company="Stripe",
        recruiter_name="Erica Gonzalez",
        recruiter_email="erica@stripe.com",
    )

    html_body = message.get_body(preferencelist=("html",)).get_content()
    plain_body = message.get_body(preferencelist=("plain",)).get_content()

    assert subject == "Software Engineer - Stripe"
    assert message["Subject"] == subject
    assert "Subject:" not in html_body
    assert "Hi Erica," in html_body
    assert "Hi Erica Gonzalez," not in html_body
    assert "LinkedIn (https://linkedin.com/in/example)" in plain_body
