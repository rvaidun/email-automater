"""Unit tests for the automate_emails.py script."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from automate_emails import (
    create_email_message,
    parse_args,
    process_string,
    schedule_send,
    save_for_followup,
)


@pytest.fixture
def mock_args():
    """Create mock command line arguments."""
    args = MagicMock()
    args.recruiter_company = "Test Company"
    args.recruiter_name = "Test Recruiter"
    args.recruiter_email = "test@example.com"
    args.subject = "Test Subject"
    args.message_body_path = "test_message.txt"
    args.timezone = "UTC"
    args.followup_db_path = "test_followup.db"
    args.followup_wait_days = 7
    args.email_address = "sender@example.com"
    args.token_path = "test_token.json"
    args.streak_token = "test_token"  # noqa: S105
    args.streak_email_address = "sender@example.com"
    args.enable_followup = True
    args.attachment_path = None
    args.attachment_name = None
    return args


@pytest.fixture
def mock_token_file(tmp_path):
    """Create a mock token file."""
    token_path = tmp_path / "test_token.json"
    token_data = {"token": "test_token"}  # noqa: S105
    with token_path.open("w") as f:
        json.dump(token_data, f)
    return token_path


@pytest.fixture
def mock_template_file(tmp_path):
    """Create a mock template file."""
    template_path = tmp_path / "test_message.txt"
    template_content = "Hello ${recruiter_name} at ${recruiter_company}"
    with template_path.open("w") as f:
        f.write(template_content)
    return template_path


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
            "--recruiter_company",
            "Test Company",
            "--recruiter_name",
            "Test Recruiter",
            "--recruiter_email",
            "test@example.com",
            "--subject",
            "Test Subject",
            "--message_body_path",
            "test_message.txt",
            "--timezone",
            "UTC",
            "--followup_db_path",
            "test_followup.db",
            "--followup_wait_days",
            "7",
            "--email_address",
            "sender@example.com",
            "--token_path",
            "test_token.json",
            "--streak_token",
            "test_token",  # noqa: S105
            "--streak_email_address",
            "sender@example.com",
            "--enable_followup",
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
        assert args.followup_db_path == "test_followup.db"
        assert args.followup_wait_days == 7
        assert args.email_address == "sender@example.com"
        assert args.token_path == "test_token.json"
        assert args.streak_token == "test_token"  # noqa: S105
        assert args.streak_email_address == "sender@example.com"
        assert args.enable_followup is True
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
        "Test content",
        "test@example.com",
        "Test Subject",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
    assert message.get_content().strip() == "Test content"


def test_create_email_message_with_attachment(mock_attachment_file):
    """Test creating an email message with an attachment."""
    message = create_email_message(
        "Test content",
        "test@example.com",
        "Test Subject",
        attachment_path=str(mock_attachment_file),
        attachment_name="Test Attachment",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
    assert message.get_content_type() == "multipart/mixed"
    parts = list(message.walk())
    assert len(parts) == 2
    assert parts[0].get_content_type() == "multipart/mixed"
    assert parts[1].get_content_type() == "text/plain"
    assert parts[1].get_content().strip() == "Test content"


def test_create_email_message_with_attachment_no_name(mock_attachment_file):
    """Test creating an email message with an attachment but no name."""
    message = create_email_message(
        "Test content",
        "test@example.com",
        "Test Subject",
        attachment_path=str(mock_attachment_file),
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
    assert message.get_content_type() == "multipart/mixed"
    parts = list(message.walk())
    assert len(parts) == 2
    assert parts[0].get_content_type() == "multipart/mixed"
    assert parts[1].get_content_type() == "text/plain"
    assert parts[1].get_content().strip() == "Test content"


def test_schedule_send_success(mock_args, mock_token_file, mock_template_file):
    """Test successful email scheduling."""
    mock_draft = {
        "message": {"threadId": "test_thread"},
        "id": "test_draft",
    }
    with (
        patch("utils.streak.schedule_send_later", return_value=True),
        patch("utils.gmail.GmailAPI") as mock_gmail,
        patch("logging.Logger.info") as mock_info,
    ):
        mock_gmail.return_value.save_draft.return_value = mock_draft
        result = schedule_send(
            mock_args,
            "Test content",
            "test_token",  # noqa: S105
            "sender@example.com",
        )
        assert result is True
        mock_info.assert_called_with("Email scheduled for later sending")


def test_schedule_send_no_token(mock_args, mock_token_file, mock_template_file):
    """Test email scheduling with no token."""
    with patch("logging.Logger.error") as mock_error:
        result = schedule_send(
            mock_args,
            "Test content",
            None,
            "sender@example.com",
        )
        assert result is False
        mock_error.assert_called_once_with("Scheduling error: No streak token provided.")


def test_save_for_followup_success(mock_args, mock_token_file, mock_template_file):
    """Test successful follow-up tracking."""
    with (
        patch("utils.followup.FollowupManager") as mock_manager,
        patch("utils.cron.setup_cron_job", return_value=True),
        patch("logging.Logger.info") as mock_info,
    ):
        result = save_for_followup(
            mock_args,
            "test@example.com",
            "Test Recruiter",
            "Test Company",
            "test_thread",
            "Test Subject",
        )
        assert result is True
        mock_info.assert_called_with("Follow-up tracking enabled")
        mock_manager.return_value.track_email.assert_called_once_with(
            "test@example.com",
            "Test Recruiter",
            "Test Company",
            "test_thread",
            "Test Subject",
            followup_wait_days=7,
            timezone="UTC",
        )


def test_save_for_followup_no_thread_id(mock_args, mock_token_file, mock_template_file):
    """Test follow-up tracking with no thread ID."""
    with patch("logging.Logger.error") as mock_error:
        result = save_for_followup(
            mock_args,
            "test@example.com",
            "Test Recruiter",
            "Test Company",
            None,
            "Test Subject",
        )
        assert result is False
        mock_error.assert_called_once_with("Follow-up tracking error: No thread ID provided.")


def test_save_for_followup_cron_setup_failed(mock_args, mock_token_file, mock_template_file):
    """Test follow-up tracking when cron setup fails."""
    with (
        patch("utils.followup.FollowupManager") as mock_manager,
        patch("utils.cron.setup_cron_job", return_value=False),
        patch("logging.Logger.error") as mock_error,
    ):
        result = save_for_followup(
            mock_args,
            "test@example.com",
            "Test Recruiter",
            "Test Company",
            "test_thread",
            "Test Subject",
        )
        assert result is False
        mock_error.assert_called_once_with("Failed to set up cron job for follow-ups")
        mock_manager.return_value.track_email.assert_not_called() 