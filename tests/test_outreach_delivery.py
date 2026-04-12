"""Tests for direct new-outreach delivery helpers."""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from utils import outreach_delivery
from utils.outreach_state import OutreachStateStore

EASTERN_TZ = ZoneInfo("America/New_York")
PARTIAL_SEND_COUNT = 2
SUCCESSFUL_SEND_COUNT = 2
DUMMY_AUTH_PATH = "unused-auth.json"
DUMMY_CREDS_PATH = "unused-creds.json"


class _FakeGmail:
    def __init__(self, *, failing_email: str | None = None) -> None:
        self.failing_email = failing_email
        self.sent_messages: list[object] = []

    def send_now(self, message: object) -> dict[str, str] | None:
        self.sent_messages.append(message)
        if self.failing_email and str(message["To"]) == self.failing_email:
            return None
        return {"threadId": f"thread-{len(self.sent_messages)}"}


def _fake_message(recipient_email: str) -> EmailMessage:
    message = EmailMessage()
    message["To"] = recipient_email
    return message


def _contact(index: int, *, company_name: str | None = None) -> dict[str, str]:
    company = company_name or f"Company {index}"
    return {
        "company_display_name": company,
        "company_key": company.lower(),
        "name": f"Recruiter {index}",
        "title": "Technical Recruiter",
        "email": f"recruiter{index}@example.com",
    }


def _run_queue_new_outreach(
    *,
    contacts: list[dict[str, str]],
    state: OutreachStateStore,
    now: datetime,
    sleep_until,
    gmail_loader,
    allowed_send_weekdays: set[int] | None = None,
) -> tuple[int, str | None]:
    """Run queue_new_outreach with the common test defaults."""
    return outreach_delivery.queue_new_outreach(
        contacts=contacts,
        state=state,
        now=now,
        token_path=DUMMY_AUTH_PATH,
        creds_path=DUMMY_CREDS_PATH,
        dry_run=False,
        is_outreach_day=True,
        send_window_timezone="America/New_York",
        allowed_send_weekdays=allowed_send_weekdays or {0, 1, 2, 3, 4},
        local_send_min_spacing_minutes=15,
        now_provider=lambda: now,
        sleep_until=sleep_until,
        gmail_loader=gmail_loader,
        email_renderer=lambda **kwargs: (
            f"Subject {kwargs['recruiter_company']}",
            _fake_message(kwargs["recruiter_email"]),
        ),
    )


def test_render_initial_email_uses_subject_template_when_no_inline_subject(
    monkeypatch,
    tmp_path,
):
    """Subject template should be used when the body file has no inline Subject line."""
    template_path = tmp_path / "body_only.html"
    template_path.write_text("<p>Hi ${recruiter_name},</p><p>Hello</p>")

    monkeypatch.setenv("MESSAGE_BODY_PATH", str(template_path))
    monkeypatch.setenv(
        "EMAIL_SUBJECT",
        "Candidate note for $company / $recruiterfirstname",
    )

    subject, message = outreach_delivery.render_initial_email(
        recruiter_company="Stripe",
        recruiter_name="Erica Gonzalez",
        recruiter_email="erica@stripe.com",
    )

    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert subject == "Candidate note for Stripe / Erica"
    assert message["Subject"] == subject
    assert "Hi Erica," in html_body


def test_queue_new_outreach_returns_outside_window_without_loading_gmail(tmp_path):
    """Outside-window sends should stop before touching Gmail."""
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    now = datetime(2026, 4, 12, 20, 0, tzinfo=EASTERN_TZ)

    queued, error = _run_queue_new_outreach(
        contacts=[
            _contact(0, company_name="Stripe")
            | {
                "email": "erica@stripe.com",
                "name": "Erica Gonzalez",
                "company_key": "stripe",
            }
        ],
        state=state,
        now=now,
        sleep_until=lambda _: None,
        gmail_loader=lambda **_: (_ for _ in ()).throw(
            AssertionError("gmail_loader should not run")
        ),
        allowed_send_weekdays={0, 1, 2, 3, 4, 6},
    )

    assert queued == 0
    assert error == "Outside the active send window for new outreach"


def test_queue_new_outreach_sends_only_times_that_fit_window(monkeypatch, tmp_path):
    """If pacing returns fewer slots than contacts, only those contacts should send."""
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    now = datetime(2026, 4, 13, 15, 0, tzinfo=EASTERN_TZ)
    fake_gmail = _FakeGmail()
    slept_until: list[datetime] = []

    monkeypatch.setattr(
        outreach_delivery,
        "paced_send_times",
        lambda *_args, **_kwargs: [
            now.replace(minute=5),
            now.replace(minute=20),
        ],
    )

    queued, error = _run_queue_new_outreach(
        contacts=[_contact(index) for index in range(3)],
        state=state,
        now=now,
        sleep_until=slept_until.append,
        gmail_loader=lambda **_: (fake_gmail, object()),
    )

    assert error is None
    assert queued == PARTIAL_SEND_COUNT
    assert len(slept_until) == PARTIAL_SEND_COUNT
    assert state.new_outreach_actions_on_day(now=now) == PARTIAL_SEND_COUNT
    assert "recruiter2@example.com" not in state.contacts


def test_queue_new_outreach_continues_after_single_send_failure(tmp_path):
    """One failed Gmail send should not block later contacts in the same run."""
    state = OutreachStateStore(tmp_path / "outreach_state.json")
    now = datetime(2026, 4, 13, 15, 0, tzinfo=EASTERN_TZ)
    fake_gmail = _FakeGmail(failing_email="recruiter1@example.com")

    queued, error = _run_queue_new_outreach(
        contacts=[_contact(index) for index in range(3)],
        state=state,
        now=now,
        sleep_until=lambda _: None,
        gmail_loader=lambda **_: (fake_gmail, object()),
    )

    assert error is None
    assert queued == SUCCESSFUL_SEND_COUNT
    assert "recruiter0@example.com" in state.contacts
    assert "recruiter1@example.com" not in state.contacts
    assert "recruiter2@example.com" in state.contacts
