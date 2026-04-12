"""Unit tests for the automate_emails.py script."""

from unittest.mock import patch

import pytest

from automate_emails import (
    create_email_message,
    parse_args,
    process_string,
    send_recruiter_email,
)
from utils.email_content import html_to_plain_text, split_inline_subject


@pytest.fixture
def mock_attachment_file(tmp_path):
    """Create a mock attachment file."""
    attachment_path = tmp_path / "test_attachment.txt"
    with attachment_path.open("w") as f:
        f.write("Test attachment content")
    return attachment_path


def test_parse_args():
    """Test argument parsing."""
    with patch(
        "sys.argv",
        [
            "automate_emails.py",
            "Test Company",
            "Test Recruiter",
            "test@example.com",
            "--subject",
            "Test Subject",
            "--message_body_path",
            "test_message.txt",
            "--timezone",
            "UTC",
            "--token_path",
            "test_token.json",
            "--attachment_path",
            "test_attachment.txt",
            "--attachment_name",
            "Test Attachment",
        ],
    ):
        args = parse_args()
        assert args.recruiter_company == "Test Company"
        assert args.recruiter_name == "Test Recruiter"
        assert args.recruiter_email == "test@example.com"
        assert args.subject == "Test Subject"
        assert args.message_body_path == "test_message.txt"
        assert args.timezone == "UTC"
        assert args.token_path == "test_token.json"  # no  # noqa: S105
        assert args.attachment_path == "test_attachment.txt"
        assert args.attachment_name == "Test Attachment"


def test_process_string():
    """Test string template processing."""
    template = "Hello ${recruiter_name} at ${recruiter_company}"
    result = process_string(
        template,
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
    )
    assert result == "Hello Test Recruiter at Test Company"


def test_create_email_message_without_attachment():
    """Test creating an email message without an attachment."""
    message = create_email_message(
        "<p>Test content</p>",
        "test@example.com",
        "Test Subject",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == (
        "Test content"
    )
    assert message.get_body(preferencelist=("html",)).get_content().strip() == (
        "<p>Test content</p>"
    )


def test_create_email_message_with_attachment(mock_attachment_file):
    """Test creating an email message with an attachment."""
    attachment_content = mock_attachment_file.read_bytes()
    message = create_email_message(
        "<p>Test content</p>",
        "test@example.com",
        "Test Subject",
        attachment=attachment_content,
        attachment_name="Test Attachment",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"


def test_create_email_message_with_attachment_no_name(mock_attachment_file):
    """Test creating an email message with an attachment but no name."""
    attachment_content = mock_attachment_file.read_bytes()
    message = create_email_message(
        "<p>Test content</p>",
        "test@example.com",
        "Test Subject",
        attachment=attachment_content,
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"


def test_html_to_plain_text_preserves_email_copy():
    """Plain-text fallback should preserve the visible message wording."""
    result = html_to_plain_text(
        "<html><body><p>Hello Jane,</p><p>Thanks<br>again.</p></body></html>"
    )

    assert result == "Hello Jane,\n\nThanks\n\nagain."


def test_html_to_plain_text_keeps_link_destinations():
    """Plain-text fallback should preserve useful link URLs."""
    result = html_to_plain_text(
        '<p><a href="https://example.com">example.com</a> | '
        '<a href="https://linkedin.com/in/example">LinkedIn</a></p>'
    )

    assert result == "example.com | LinkedIn (https://linkedin.com/in/example)"


def test_split_inline_subject_removes_subject_paragraph():
    """Inline Subject paragraphs should become headers, not body copy."""
    subject, body = split_inline_subject(
        "<p>Subject: Hello Stripe</p><p>Hi Jane,</p><p>Body</p>"
    )

    assert subject == "Hello Stripe"
    assert body == "<p>Hi Jane,</p><p>Body</p>"


def test_send_recruiter_email_uses_real_template_inline_subject(monkeypatch):
    """Real send builder should use email1's inline subject and first-name greeting."""
    captured: dict[str, object] = {}

    class FakeGmail:
        def send_now(self, message: object) -> dict[str, str]:
            captured["message"] = message
            return {"threadId": "thread-1"}

    monkeypatch.setattr(
        "automate_emails.load_authenticated_gmail",
        lambda **_: (FakeGmail(), object()),
    )

    result = send_recruiter_email(
        recruiter_company="Stripe",
        recruiter_name="Erica Gonzalez",
        recruiter_email="erica@stripe.com",
        subject_template=None,
        message_body_path="email1.md",
    )

    message = captured["message"]
    html_body = message.get_body(preferencelist=("html",)).get_content()
    plain_body = message.get_body(preferencelist=("plain",)).get_content()

    assert result == {"threadId": "thread-1"}
    assert message["Subject"] == "Software Engineer - Stripe"
    assert "Subject:" not in html_body
    assert "Hi Erica," in html_body
    assert "Hi Erica Gonzalez," not in html_body
    assert "LinkedIn (https://linkedin.com/in/example)" in plain_body


def test_send_recruiter_email_tracks_followup_with_inline_subject(monkeypatch):
    """Follow-up tracking should store the same resolved inline subject."""
    tracked: dict[str, str] = {}

    class FakeGmail:
        def send_now(self, _message: object) -> dict[str, str]:
            return {"threadId": "thread-1"}

    def fake_track_email(*args: object, **kwargs: object) -> None:
        del kwargs
        tracked["subject"] = str(args[4])

    monkeypatch.setattr(
        "automate_emails.load_authenticated_gmail",
        lambda **_: (FakeGmail(), object()),
    )
    monkeypatch.setattr("automate_emails.track_email", fake_track_email)

    send_recruiter_email(
        recruiter_company="Stripe",
        recruiter_name="Erica Gonzalez",
        recruiter_email="erica@stripe.com",
        subject_template=None,
        message_body_path="email1.md",
        enable_followup=True,
    )

    assert tracked["subject"] == "Software Engineer - Stripe"


def test_send_recruiter_email_requires_subject_from_template_or_arg(tmp_path):
    """Templates without inline subject should still require an explicit subject."""
    template_path = tmp_path / "body_only.html"
    template_path.write_text("<p>Hi ${recruiter_name},</p><p>Hello</p>")

    class FakeGmail:
        def send_now(self, _message: object) -> dict[str, str]:
            return {"threadId": "thread-1"}

    with (
        patch(
            "automate_emails.load_authenticated_gmail",
            return_value=(FakeGmail(), object()),
        ),
        pytest.raises(
            ValueError,
            match=(
                "Email subject is required via template Subject line or EMAIL_SUBJECT"
            ),
        ),
    ):
        send_recruiter_email(
            recruiter_company="Stripe",
            recruiter_name="Erica Gonzalez",
            recruiter_email="erica@stripe.com",
            subject_template=None,
            message_body_path=template_path,
        )
