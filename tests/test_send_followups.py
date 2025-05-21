"""Unit tests for the send_followups.py script."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from send_followups import (
    create_email_message,
    parse_args,
    process_string,
)


@pytest.fixture
def mock_args():
    """Create mock command line arguments."""
    args = MagicMock()
    args.followup_body_path = "test_followup.txt"
    args.followup_subject = "Test Follow-up"
    args.timezone = "UTC"
    args.followup_db_path = "test_followup.db"
    args.followup_wait_days = 7
    args.email_address = "sender@example.com"
    args.token_path = "test_token.json"
    args.streak_token = "test_token"  # noqa: S105
    args.streak_email_address = "sender@example.com"
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
    template_path = tmp_path / "test_followup.txt"
    template_content = "Hello ${recruiter_name} at ${recruiter_company}"
    with template_path.open("w") as f:
        f.write(template_content)
    return template_path


def test_parse_args():
    """Test argument parsing."""
    with patch(
        "sys.argv",
        [
            "send_followups.py",
            "--followup_body_path",
            "test_followup.txt",
            "--followup_subject",
            "Test Follow-up",
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
        ],
    ), patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_parse.return_value = mock_args()
        args = parse_args()
        assert args.followup_body_path == "test_followup.txt"
        assert args.followup_subject == "Test Follow-up"
        assert args.timezone == "UTC"
        assert args.followup_db_path == "test_followup.db"
        assert args.followup_wait_days == 7
        assert args.email_address == "sender@example.com"
        assert args.token_path == "test_token.json"
        assert args.streak_token == "test_token"  # noqa: S105
        assert args.streak_email_address == "sender@example.com"


def test_create_email_message():
    """Test creating an email message."""
    message = create_email_message(
        "Test content",
        "test@example.com",
        "Test Follow-up",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Follow-up"
    assert message.get_content().strip() == "Test content"


def test_process_string():
    """Test string template processing."""
    template = "Hello ${recruiter_name} at ${recruiter_company}"
    result = process_string(
        template,
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
    )
    assert result == "Hello Test Recruiter at Test Company"


def test_main_no_pending_followups(mock_args, mock_token_file, mock_template_file):
    """Test main function with no pending follow-ups."""
    with (
        patch("send_followups.parse_args", return_value=mock_args),
        patch("utils.followup.FollowupManager") as mock_manager,
        patch("utils.gmail.GmailAPI") as mock_gmail,
        patch("logging.Logger.info") as mock_info,
    ):
        mock_manager.return_value.get_pending_followups.return_value = []
        from send_followups import main
        main()
        mock_info.assert_called_with("No pending follow-ups found")


def test_main_with_pending_followups(
    mock_args, mock_token_file, mock_template_file
):
    """Test main function with pending follow-ups."""
    mock_followup = {
        "recruiter_email": "test@example.com",
        "recruiter_name": "Test Recruiter",
        "recruiter_company": "Test Company",
        "thread_id": "test_thread",
        "subject": "Test Subject",
        "followup_count": 0,
    }
    mock_draft = {
        "message": {"threadId": "test_thread"},
        "id": "test_draft",
    }
    with (
        patch("send_followups.parse_args", return_value=mock_args),
        patch("utils.followup.FollowupManager") as mock_manager,
        patch("utils.gmail.GmailAPI") as mock_gmail,
        patch("utils.streak.schedule_send_later") as mock_schedule,
        patch("logging.Logger.info") as mock_info,
    ):
        mock_manager.return_value.get_pending_followups.return_value = [mock_followup]
        mock_gmail.return_value.save_draft.return_value = mock_draft
        from send_followups import main
        main()
        mock_info.assert_called_with("Found 1 pending follow-ups")
        mock_manager.return_value.update_followup_status.assert_called_once_with(
            "test@example.com"
        ) 