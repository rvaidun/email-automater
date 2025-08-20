"""Unit tests for the automate_emails.py script."""

import json
from unittest.mock import MagicMock, patch

import pytest

from automate_emails import (
    create_email_message,
    parse_args,
    process_string,
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
    args.email_address = "sender@example.com"
    args.token_path = "test_token.json"  # noqa: S105
    args.streak_token = "test_token"  # noqa: S105
    args.streak_email_address = "sender@example.com"
    args.attachment_path = None
    args.attachment_name = None
    return args


@pytest.fixture
def mock_token_file(tmp_path):
    """Create a mock token file."""
    token_path = tmp_path / "test_token.json"
    token_data = {"token": "test_token"}
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
            "Test Company",
            "Test Recruiter",
            "test@example.com",
            "--subject",
            "Test Subject",
            "--message_body_path",
            "test_message.txt",
            "--timezone",
            "UTC",
            "7",
            "--email_address",
            "sender@example.com",
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
        assert args.email_address == "sender@example.com"
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
        "Test content",
        "test@example.com",
        "Test Subject",
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
    assert message.get_content().strip() == "Test content"


def test_create_email_message_with_attachment(mock_attachment_file):
    """Test creating an email message with an attachment."""
    attachment_content = mock_attachment_file.read_bytes()
    message = create_email_message(
        "Test content",
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
        "Test content",
        "test@example.com",
        "Test Subject",
        attachment=attachment_content,
    )
    assert message["To"] == "test@example.com"
    assert message["Subject"] == "Test Subject"
