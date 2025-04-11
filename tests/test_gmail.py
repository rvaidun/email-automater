"""Unit tests for the GmailAPI class."""

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from utils.gmail import GmailAPI


@pytest.fixture
def gmail_api():
    """Fixture to provide a GmailAPI instance."""
    return GmailAPI()


@pytest.fixture
def mock_credentials():
    """Fixture to provide mock credentials."""
    creds = MagicMock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    return creds


@pytest.fixture
def mock_email_message():
    """Fixture to provide a mock email message."""
    message = EmailMessage()
    message["From"] = "test@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Test Subject"
    message.set_content("Test content")
    return message


def test_login_with_valid_token(gmail_api, mock_credentials):
    """Test login with valid token."""
    with patch("utils.gmail.Credentials.from_authorized_user_info") as mock_from_auth:
        mock_from_auth.return_value = mock_credentials
        with patch("utils.gmail.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            result = gmail_api.login({"token": "test_token"})

            assert result == mock_credentials
            assert gmail_api.service == mock_service
            mock_build.assert_called_once_with(
                "gmail", "v1", credentials=mock_credentials, cache_discovery=False
            )


def test_login_with_expired_token(gmail_api, mock_credentials):
    """Test login with expired token that needs refreshing."""
    mock_credentials.valid = False
    mock_credentials.expired = True
    mock_credentials.refresh_token = "refresh_token"  # noqa: S105

    with patch("utils.gmail.Credentials.from_authorized_user_info") as mock_from_auth:
        mock_from_auth.return_value = mock_credentials
        with (
            patch("utils.gmail.Request") as mock_request,
            patch("utils.gmail.build") as mock_build,
        ):
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            result = gmail_api.login({"token": "test_token"})

            assert result == mock_credentials
            assert gmail_api.service == mock_service
            mock_credentials.refresh.assert_called_once_with(mock_request.return_value)
            mock_build.assert_called_once_with(
                "gmail", "v1", credentials=mock_credentials, cache_discovery=False
            )


def test_save_draft_success(gmail_api, mock_email_message):
    """Test successful draft saving."""
    mock_service = MagicMock()
    mock_draft = {"id": "draft123"}
    mock_service.users.return_value.drafts.return_value.create.return_value.execute.return_value = mock_draft
    gmail_api.service = mock_service

    result = gmail_api.save_draft(mock_email_message)

    assert result == mock_draft
    mock_service.users.return_value.drafts.return_value.create.assert_called_once()


def test_save_draft_failure(gmail_api, mock_email_message):
    """Test draft saving failure."""
    mock_service = MagicMock()
    mock_service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
        resp=MagicMock(), content=b"Error"
    )
    gmail_api.service = mock_service

    result = gmail_api.save_draft(mock_email_message)

    assert result is False


def test_send_now_success(gmail_api, mock_email_message):
    """Test successful message sending."""
    mock_service = MagicMock()
    mock_sent = {"id": "message123"}
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = mock_sent
    gmail_api.service = mock_service

    result = gmail_api.send_now(mock_email_message)

    assert result == mock_sent
    mock_service.users.return_value.messages.return_value.send.assert_called_once()


def test_send_now_failure(gmail_api, mock_email_message):
    """Test message sending failure."""
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        resp=MagicMock(), content=b"Error"
    )
    gmail_api.service = mock_service

    result = gmail_api.send_now(mock_email_message)

    assert result is False


def test_get_current_user(gmail_api):
    """Test getting current user information."""
    mock_service = MagicMock()
    mock_user_info = {"emailAddress": "test@example.com"}
    mock_service.users.return_value.getProfile.return_value.execute.return_value = (
        mock_user_info
    )
    gmail_api.service = mock_service

    result = gmail_api.get_current_user()

    assert result == mock_user_info
    mock_service.users.return_value.getProfile.assert_called_once_with(userId="me")
