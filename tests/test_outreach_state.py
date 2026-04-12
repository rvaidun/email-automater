"""Tests for outreach state management."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.outreach_state import OutreachStateStore


def test_mark_contact_queued_sets_cooldown_and_due_followup(tmp_path):
    """Queued outreach should create company cooldown and follow-up timing."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 11, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    store.mark_company_seen("Stripe", source="newgrad-jobs", seen_at=now)
    allowed, reason = store.can_contact_company("stripe", now=now)
    assert allowed is True
    assert reason == ""

    store.mark_contact_queued(
        email="jane@stripe.com",
        company_name="Stripe",
        name="Jane Doe",
        title="Technical Recruiter",
        thread_id="thread-1",
        source="apollo",
        scheduled_for=now,
    )

    allowed, reason = store.can_contact_company("stripe", now=now)
    assert allowed is False
    assert reason in {"cooldown", "daily_limit"}

    due = store.due_followups(now=now + timedelta(days=3, minutes=1))
    assert len(due) == 1
    assert due[0]["email"] == "jane@stripe.com"


def test_mark_followup_sent_closes_after_second_followup(tmp_path):
    """Contacts should close after the second follow-up."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 11, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    store.mark_contact_sent(
        email="jane@stripe.com",
        company_name="Stripe",
        name="Jane Doe",
        title="Technical Recruiter",
        thread_id="thread-1",
        source="apollo",
        sent_at=now,
    )

    store.mark_followup_sent("jane@stripe.com", sent_at=now + timedelta(days=3))
    assert store.contacts["jane@stripe.com"]["status"] == "sent"

    store.mark_followup_sent("jane@stripe.com", sent_at=now + timedelta(days=6))
    assert store.contacts["jane@stripe.com"]["status"] == "closed"
    assert store.contacts["jane@stripe.com"]["next_followup_at"] is None


def test_due_followups_use_due_date_not_exact_timestamp(tmp_path):
    """Daily 3 PM runs should still catch contacts sent later in the afternoon."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    sent_at = datetime(2026, 4, 12, 16, 20, tzinfo=ZoneInfo("America/New_York"))
    run_time = datetime(2026, 4, 15, 15, 0, tzinfo=ZoneInfo("America/New_York"))

    store.mark_contact_sent(
        email="late@stripe.com",
        company_name="Stripe",
        name="Late Recruiter",
        title="Technical Recruiter",
        thread_id="thread-late",
        source="apollo",
        sent_at=sent_at,
    )

    due = store.due_followups(now=run_time)

    assert len(due) == 1
    assert due[0]["email"] == "late@stripe.com"


def test_new_outreach_actions_on_day_counts_action_time(tmp_path):
    """Daily outreach counts should use the day the action actually happened."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("America/New_York"))

    store.mark_contact_queued(
        email="jane@stripe.com",
        company_name="Stripe",
        name="Jane Doe",
        title="Technical Recruiter",
        thread_id="thread-1",
        source="apollo",
        scheduled_for=now + timedelta(days=2),
        actioned_at=now,
    )

    assert store.new_outreach_actions_on_day(now=now) == 1
