"""Unit tests for the streak module."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from utils.streak import StreakSendLaterConfig, schedule_send_later


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return StreakSendLaterConfig(
        token="test_token",  # noqa: S106 # This is a test token, not a real one
        to_address="test@example.com",
        subject="Test Subject",
        thread_id="test_thread",
        draft_id="test_draft",
        send_date=datetime.datetime(2024, 4, 10, 12, 0, 0, tzinfo=datetime.UTC),
        is_tracked=True,
        email_address="sender@example.com",
    )


def test_schedule_send_later_success(mock_config):
    """Test successful scheduling of an email."""
    # Create a mock response
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.text = "Success"

    # Patch requests.post to return our mock response
    with patch("requests.post", return_value=mock_response) as mock_post:
        result = schedule_send_later(mock_config)

        # Verify the function returned True
        assert result is True

        # Verify the correct URL was called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.streak.com/api/v2/sendlaters"

        # Verify the headers were set correctly
        assert kwargs["headers"]["authorization"] == "Bearer test_token"

        # Verify the data was formatted correctly
        data = kwargs["data"]
        assert data["threadId"] == "test_thread"
        assert data["draftId"] == "test_draft"
        assert data["subject"] == "Test Subject"
        assert data["isTracked"] == "true"
        assert data["toAddresses"] == '["test@example.com"]'

        # Verify the timestamp conversion
        expected_timestamp = int(
            datetime.datetime(2024, 4, 10, 12, 0, 0, tzinfo=datetime.UTC).timestamp()
            * 1000
        )
        assert int(data["sendDate"]) == expected_timestamp


def test_schedule_send_later_failure(mock_config):
    """Test failed scheduling of an email."""
    # Create a mock response that indicates failure
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.text = "Error message"

    # Patch requests.post to return our mock response
    with patch("requests.post", return_value=mock_response) as mock_post:
        result = schedule_send_later(mock_config)

        # Verify the function returned False
        assert result is False

        # Verify the API was called
        mock_post.assert_called_once()


def test_schedule_send_later_timezone_conversion():
    """Test that the send date is properly converted to UTC."""
    # Create a config with a non-UTC timezone
    local_time = datetime.datetime(2024, 4, 10, 12, 0, 0)
    local_time = local_time.replace(
        tzinfo=datetime.timezone(datetime.timedelta(hours=-4))
    )  # EDT

    config = StreakSendLaterConfig(
        token="test_token",  # noqa: S106 # This is a test token, not a real one
        to_address="test@example.com",
        subject="Test Subject",
        thread_id="test_thread",
        draft_id="test_draft",
        send_date=local_time,
        is_tracked=True,
        email_address="sender@example.com",
    )

    # Create a mock response
    mock_response = MagicMock()
    mock_response.ok = True

    with patch("requests.post", return_value=mock_response) as mock_post:
        schedule_send_later(config)

        # Get the timestamp that was sent
        args, kwargs = mock_post.call_args
        sent_timestamp = int(kwargs["data"]["sendDate"])

        # Calculate the expected UTC timestamp
        expected_utc = local_time.astimezone(datetime.UTC)
        expected_timestamp = int(expected_utc.timestamp() * 1000)

        # Verify the timestamps match
        assert sent_timestamp == expected_timestamp


def test_schedule_send_later_network_error(mock_config):
    """Test handling of network errors."""
    # Patch requests.post to raise an exception
    with patch("requests.post", side_effect=requests.RequestException("Network error")):
        result = schedule_send_later(mock_config)
        assert result is False
