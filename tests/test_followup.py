"""Unit tests for the follow-up management functionality."""

import datetime
from unittest.mock import patch

import pytest

from utils.followup import FollowupManager


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_followup.db"


@pytest.fixture
def followup_manager(temp_db_path):
    """Create a FollowupManager instance with a temporary database."""
    return FollowupManager(db_path=str(temp_db_path))


def test_init_creates_db(temp_db_path):
    """Test that database is created on initialization."""
    assert temp_db_path.exists()
    assert temp_db_path.stat().st_size > 0


def test_track_new_email(followup_manager):
    """Test tracking a new email."""
    now = datetime.datetime.now(datetime.UTC)
    default_followup_wait_days = 3
    default_max_followups = 2
    followup_manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
        thread_id="test_thread",
        followup_wait_days=default_followup_wait_days,
        max_followups=default_max_followups,
        timezone="UTC",
    )

    # Verify email was tracked
    status = followup_manager.get_email_status("test@example.com")
    assert status is not None
    assert status["recruiter_email"] == "test@example.com"
    assert status["recruiter_name"] == "Test Recruiter"
    assert status["recruiter_company"] == "Test Company"
    assert status["thread_id"] == "test_thread"
    assert status["followup_count"] == 0
    assert status["max_followups"] == default_max_followups
    assert status["followup_wait_days"] == default_followup_wait_days
    assert status["timezone"] == "UTC"

    # Verify timestamps
    next_followup = datetime.datetime.fromisoformat(status["next_followup"])
    assert abs((next_followup - (now + datetime.timedelta(days=3))).total_seconds()) < 1


def test_track_existing_email(followup_manager):
    """Test tracking an email that already exists."""
    # First track
    followup_manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
        thread_id="test_thread_1",
    )

    # Try to track again
    followup_manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
        thread_id="test_thread_2",
    )

    # Verify original data was preserved
    status = followup_manager.get_email_status("test@example.com")
    assert status["thread_id"] == "test_thread_1"


def test_get_pending_followups(followup_manager):
    """Test getting pending follow-ups."""
    # Add some emails with different follow-up dates
    now = datetime.datetime.now(datetime.UTC)
    past = (now - datetime.timedelta(days=1)).isoformat()
    future = (now + datetime.timedelta(days=1)).isoformat()

    # Email 1: Due for follow-up
    followup_manager.track_email(
        recruiter_email="test1@example.com",
        recruiter_name="Test Recruiter 1",
        recruiter_company="Test Company 1",
        thread_id="test_thread_1",
    )
    with followup_manager._get_connection() as conn:  # noqa: SLF001
        conn.execute(
            "UPDATE emails SET next_followup = ? WHERE recruiter_email = ?",
            (past, "test1@example.com"),
        )
        conn.commit()

    # Email 2: Not due yet
    followup_manager.track_email(
        recruiter_email="test2@example.com",
        recruiter_name="Test Recruiter 2",
        recruiter_company="Test Company 2",
        thread_id="test_thread_2",
    )
    with followup_manager._get_connection() as conn:  # noqa: SLF001
        conn.execute(
            "UPDATE emails SET next_followup = ? WHERE recruiter_email = ?",
            (future, "test2@example.com"),
        )
        conn.commit()

    # Email 3: Due but max follow-ups reached
    followup_manager.track_email(
        recruiter_email="test3@example.com",
        recruiter_name="Test Recruiter 3",
        recruiter_company="Test Company 3",
        thread_id="test_thread_3",
        max_followups=1,
    )
    with followup_manager._get_connection() as conn:  # noqa: SLF001
        conn.execute(
            """
            UPDATE emails
            SET next_followup = ?, followup_count = 1
            WHERE recruiter_email = ?
            """,
            (past, "test3@example.com"),
        )
        conn.commit()

    # Get pending follow-ups
    pending = followup_manager.get_pending_followups()

    # Should only get email1 (email2 is not due, email3 has reached max follow-ups)
    assert len(pending) == 1
    assert pending[0]["recruiter_email"] == "test1@example.com"


def test_update_followup_status(followup_manager):
    """Test updating follow-up status."""
    # Track an email
    followup_manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Company",
        thread_id="test_thread",
        followup_wait_days=3,
    )

    # Get initial status
    initial_status = followup_manager.get_email_status("test@example.com")
    initial_count = initial_status["followup_count"]

    # Update status
    followup_manager.update_followup_status("test@example.com")

    # Get updated status
    updated_status = followup_manager.get_email_status("test@example.com")
    assert updated_status["followup_count"] == initial_count + 1

    # Verify next follow-up was updated
    updated_next = datetime.datetime.fromisoformat(updated_status["next_followup"])
    expected_next = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=3)
    assert abs((updated_next - expected_next).total_seconds()) < 1


def test_update_nonexistent_email(followup_manager):
    """Test updating status for non-existent email."""
    with patch("logging.Logger.warning") as mock_warning:
        followup_manager.update_followup_status("nonexistent@example.com")
        mock_warning.assert_called_once_with(
            "Email to %s not found in tracking database", "nonexistent@example.com"
        )


def test_get_email_status_nonexistent(followup_manager):
    """Test getting status for non-existent email."""
    status = followup_manager.get_email_status("nonexistent@example.com")
    assert status is None
