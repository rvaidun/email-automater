"""Tests for reply detection logic."""

import base64

from utils.reply_detection import detect_thread_stop


def _message(from_header: str, subject: str, body: str = "") -> dict[str, object]:
    encoded_body = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return {
        "snippet": body,
        "payload": {
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": subject},
            ],
            "body": {"data": encoded_body},
        },
    }


def test_detect_thread_reply():
    """A recruiter reply should stop future follow-ups."""
    thread = {
        "messages": [
            _message("Sender <me@example.com>", "Software Engineer - Stripe", "Hi"),
            _message(
                "Jane Doe <jane@stripe.com>",
                "Re: Software Engineer - Stripe",
                "Thanks for reaching out",
            ),
        ]
    }

    result = detect_thread_stop(
        thread,
        sender_email="me@example.com",
        recipient_email="jane@stripe.com",
    )

    assert result.stop is True
    assert result.status == "replied"


def test_detect_thread_bounce():
    """A bounce should be marked and stop future follow-ups."""
    thread = {
        "messages": [
            _message(
                "Mail Delivery Subsystem <mailer-daemon@example.com>",
                "Delivery Status Notification",
                "Your message could not be delivered",
            )
        ]
    }

    result = detect_thread_stop(
        thread,
        sender_email="me@example.com",
        recipient_email="jane@stripe.com",
    )

    assert result.stop is True
    assert result.status == "bounced"


def test_detect_thread_opt_out():
    """An opt-out reply should stop future follow-ups."""
    thread = {
        "messages": [
            _message(
                "Jane Doe <jane@stripe.com>",
                "Re: Software Engineer - Stripe",
                "Please remove me from future outreach.",
            )
        ]
    }

    result = detect_thread_stop(
        thread,
        sender_email="me@example.com",
        recipient_email="jane@stripe.com",
    )

    assert result.stop is True
    assert result.status == "opt_out"
