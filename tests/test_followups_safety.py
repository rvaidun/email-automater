"""Safety tests for follow-up processing defaults."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import send_followups
from utils.followup import load_template
from utils.outreach_state import OutreachStateStore

DUE_FOLLOWUPS = 7
PACED_SEND_COUNT = 3


class _FakeGmail:
    def __init__(self) -> None:
        self.sent_messages: list[object] = []

    def get_current_user(self) -> dict[str, str]:
        return {"emailAddress": "sender@example.com"}

    def get_thread(self, _thread_id: str) -> dict[str, object]:
        return {
            "messages": [
                {
                    "payload": {
                        "headers": [
                            {
                                "name": "Subject",
                                "value": "Software Engineer - Example",
                            }
                        ]
                    }
                }
            ]
        }

    def send_now(
        self,
        message: object,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        self.sent_messages.append(message)
        return {"threadId": thread_id or "thread"}


def _no_stop_detection(*_: object, **__: object) -> object:
    return type(
        "Detection",
        (),
        {"stop": False, "status": "none", "reply_status": "none"},
    )()


def _mark_contact_sent(
    store: OutreachStateStore,
    *,
    email: str,
    now: datetime,
    company_name: str = "Example",
    name: str = "Recruiter",
    title: str = "Technical Recruiter",
    thread_id: str = "thread-1",
) -> None:
    store.mark_contact_sent(
        email=email,
        company_name=company_name,
        name=name,
        title=title,
        thread_id=thread_id,
        source="apollo",
        sent_at=now,
    )


def _patch_followup_runtime(
    monkeypatch,
    store: OutreachStateStore,
    *,
    now: datetime,
    gmail: _FakeGmail | None = None,
    sleep_until: object | None = None,
    detection: object = _no_stop_detection,
    weekdays: str = "0,1,2,3,4",
) -> _FakeGmail:
    """Patch the common follow-up runtime hooks for safety tests."""
    fake_gmail = gmail or _FakeGmail()
    monkeypatch.setattr(store, "now", lambda: now)
    monkeypatch.setenv("FOLLOWUP_WEEKDAYS", weekdays)
    monkeypatch.setattr(send_followups, "_now", lambda: now)
    monkeypatch.setattr(
        send_followups,
        "_sleep_until",
        sleep_until if sleep_until is not None else (lambda *_: None),
    )
    monkeypatch.setattr(
        send_followups,
        "load_authenticated_gmail",
        lambda **_: (fake_gmail, object()),
    )
    if detection is not None:
        monkeypatch.setattr(send_followups, "detect_thread_stop", detection)
    return fake_gmail


def _process_followups(state_path, store: OutreachStateStore) -> dict[str, int]:
    """Run follow-up processing against the prepared test store."""
    return send_followups.process_followups(
        state_path=str(state_path),
        dry_run=False,
        state_store=store,
    )


def _setup_erica_contact(
    store: OutreachStateStore,
    *,
    now: datetime,
    days_ago: int,
) -> None:
    _mark_contact_sent(
        store,
        email="erica@example.com",
        company_name="Stripe",
        name="Erica Gonzalez",
        now=now - timedelta(days=days_ago),
    )


def test_process_followups_is_unlimited_by_default(monkeypatch, tmp_path):
    """Unset follow-up caps should process every due thread."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 13, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    for index in range(DUE_FOLLOWUPS):
        _mark_contact_sent(
            store,
            email=f"recruiter{index}@example.com",
            company_name=f"Company {index}",
            name=f"Recruiter {index}",
            thread_id=f"thread-{index}",
            now=now - timedelta(days=4),
        )
    store.save()
    monkeypatch.delenv("FOLLOWUP_DAILY_LIMIT", raising=False)
    _patch_followup_runtime(monkeypatch, store, now=now)

    summary = _process_followups(state_path, store)

    assert summary["followups_sent"] == DUE_FOLLOWUPS


def test_process_followups_defers_sunday_sends(monkeypatch, tmp_path):
    """Weekend runs should leave due follow-ups pending."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 12, 10, 15, tzinfo=ZoneInfo("America/New_York"))

    _mark_contact_sent(
        store,
        email="recruiter@example.com",
        now=now - timedelta(days=4),
    )
    store.save()
    _patch_followup_runtime(monkeypatch, store, now=now)

    summary = _process_followups(state_path, store)

    assert summary["followups_sent"] == 0
    assert store.contacts["recruiter@example.com"]["followup_count"] == 0


def test_process_followups_paces_sends_across_business_window(monkeypatch, tmp_path):
    """Follow-ups should be paced instead of sending as one burst."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 13, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    slept_until: list[datetime] = []

    for index in range(PACED_SEND_COUNT):
        _mark_contact_sent(
            store,
            email=f"recruiter{index}@example.com",
            company_name=f"Company {index}",
            name=f"Recruiter {index}",
            thread_id=f"thread-{index}",
            now=now - timedelta(days=4),
        )
    store.save()
    _patch_followup_runtime(
        monkeypatch,
        store,
        now=now,
        sleep_until=slept_until.append,
    )

    summary = _process_followups(state_path, store)

    assert summary["followups_sent"] == PACED_SEND_COUNT
    assert len(slept_until) == PACED_SEND_COUNT
    assert slept_until == sorted(slept_until)


def test_followup_templates_use_email2_then_email3():
    """Default follow-up templates should progress in the requested order."""
    first_followup = load_template(followup_count=0)
    second_followup = load_template(followup_count=1)

    assert "Didn't want my earlier note" in first_followup
    assert "Last note from me" in second_followup


def test_process_followups_uses_email2_content_for_first_followup(
    monkeypatch,
    tmp_path,
):
    """First follow-up sends should render email2 with first-name greeting only."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 13, 10, 15, tzinfo=ZoneInfo("America/New_York"))
    fake_gmail = _FakeGmail()

    _setup_erica_contact(store, now=now, days_ago=4)
    store.save()
    _patch_followup_runtime(monkeypatch, store, now=now, gmail=fake_gmail)

    summary = _process_followups(state_path, store)

    message = fake_gmail.sent_messages[0]
    html_body = message.get_body(preferencelist=("html",)).get_content()

    assert summary["followups_sent"] == 1
    assert message["Subject"] == "Re: Software Engineer - Example"
    assert "Didn't want my earlier note" in html_body
    assert "Hi Erica," in html_body
    assert "Hi Erica Gonzalez," not in html_body
    assert "Subject:" not in html_body


def test_process_followups_uses_email3_content_for_second_followup(
    monkeypatch,
    tmp_path,
):
    """Second follow-up sends should render email3 when followup_count is already 1."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 16, 10, 15, tzinfo=ZoneInfo("America/New_York"))
    fake_gmail = _FakeGmail()

    _setup_erica_contact(store, now=now, days_ago=6)
    contact = store.contacts["erica@example.com"]
    contact["followup_count"] = 1
    contact["next_followup_at"] = (now - timedelta(minutes=5)).isoformat()
    store.contacts["erica@example.com"] = contact
    store.save()
    _patch_followup_runtime(monkeypatch, store, now=now, gmail=fake_gmail)

    summary = _process_followups(state_path, store)

    message = fake_gmail.sent_messages[0]
    html_body = message.get_body(preferencelist=("html",)).get_content()

    assert summary["followups_sent"] == 1
    assert message["Subject"] == "Re: Software Engineer - Example"
    assert "Last note from me" in html_body
    assert "Didn't want my earlier note" not in html_body
    assert "Hi Erica," in html_body
    assert "Subject:" not in html_body


def test_process_followups_marks_reply_and_skips_send(monkeypatch, tmp_path):
    """A recruiter reply should close the contact without sending a follow-up."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 13, 10, 15, tzinfo=ZoneInfo("America/New_York"))
    fake_gmail = _FakeGmail()
    thread = {
        "messages": [
            {
                "snippet": "Hi",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Sender <sender@example.com>"},
                        {"name": "Subject", "value": "Software Engineer - Stripe"},
                    ]
                },
            },
            {
                "snippet": "Thanks for reaching out",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Erica <erica@example.com>"},
                        {"name": "Subject", "value": "Re: Software Engineer - Stripe"},
                    ]
                },
            },
        ]
    }

    _setup_erica_contact(store, now=now, days_ago=4)
    store.save()
    _patch_followup_runtime(
        monkeypatch,
        store,
        now=now,
        gmail=fake_gmail,
        detection=None,
    )
    monkeypatch.setattr(fake_gmail, "get_thread", lambda _thread_id: thread)

    summary = _process_followups(state_path, store)

    assert summary["followups_sent"] == 0
    assert summary["replies_detected"] == 1
    assert fake_gmail.sent_messages == []
    assert store.contacts["erica@example.com"]["status"] == "replied"
    assert store.contacts["erica@example.com"]["next_followup_at"] is None


def test_process_followups_marks_bounce_and_skips_send(monkeypatch, tmp_path):
    """A bounce should stop follow-ups and mark the contact as bounced."""
    state_path = tmp_path / "outreach_state.json"
    store = OutreachStateStore(state_path)
    now = datetime(2026, 4, 13, 10, 15, tzinfo=ZoneInfo("America/New_York"))
    fake_gmail = _FakeGmail()
    thread = {
        "messages": [
            {
                "snippet": "Delivery Status Notification",
                "payload": {
                    "headers": [
                        {
                            "name": "From",
                            "value": (
                                "Mail Delivery Subsystem <mailer-daemon@example.com>"
                            ),
                        },
                        {
                            "name": "Subject",
                            "value": "Delivery Status Notification",
                        },
                    ]
                },
            }
        ]
    }

    _setup_erica_contact(store, now=now, days_ago=4)
    store.save()
    _patch_followup_runtime(
        monkeypatch,
        store,
        now=now,
        gmail=fake_gmail,
        detection=None,
    )
    monkeypatch.setattr(fake_gmail, "get_thread", lambda _thread_id: thread)

    summary = _process_followups(state_path, store)

    assert summary["followups_sent"] == 0
    assert summary["bounces_detected"] == 1
    assert fake_gmail.sent_messages == []
    assert store.contacts["erica@example.com"]["status"] == "bounced"
    assert store.contacts["erica@example.com"]["next_followup_at"] is None
