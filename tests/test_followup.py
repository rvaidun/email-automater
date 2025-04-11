import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from utils.followup import FollowupManager, default_manager


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        # Initialize with empty database structure
        json.dump({"emails": []}, f)
        f.flush()
        yield f.name
    os.unlink(f.name)  # noqa: PTH108


@pytest.fixture
def manager(temp_db):
    """Create a FollowupManager instance with a temporary database."""
    return FollowupManager(db_path=temp_db, followup_wait_days=3, timezone="UTC")


def test_initialization(manager):
    """Test FollowupManager initialization."""
    assert manager.db_path.exists()
    assert manager.followup_wait_days == 3  # noqa: PLR2004
    assert manager.timezone == ZoneInfo("UTC")


def test_load_empty_db(manager):
    """Test loading an empty database."""
    db = manager.load_followup_db()
    assert db == {"emails": []}


def test_track_email(manager):
    """Test tracking a new email."""
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    db = manager.load_followup_db()
    assert len(db["emails"]) == 1
    email = db["emails"][0]
    assert email["recruiter_email"] == "test@example.com"
    assert email["recruiter_name"] == "Test Recruiter"
    assert email["recruiter_company"] == "Test Corp"
    assert email["thread_id"] == "123"
    assert email["subject"] == "Test Subject"
    assert email["followup_count"] == 0
    assert "initial_contact" in email
    assert "last_contact" in email
    assert "next_followup" in email


def test_track_existing_email(manager):
    """Test updating an existing email entry."""
    # First track
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    # Track again with different thread_id
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="456",
        subject="Test Subject",
    )

    db = manager.load_followup_db()
    assert len(db["emails"]) == 1
    assert db["emails"][0]["thread_id"] == "456"


def test_get_pending_followups(manager):
    """Test getting pending follow-ups."""
    # Add an email that's due for follow-up
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    # Modify the next_followup to be in the past
    db = manager.load_followup_db()
    db["emails"][0]["next_followup"] = (
        datetime.now(ZoneInfo("UTC")) - timedelta(days=1)
    ).isoformat()
    manager.save_followup_db(db)

    pending = manager.get_pending_followups()
    assert len(pending) == 1
    assert pending[0]["recruiter_email"] == "test@example.com"


def test_update_followup_status(manager):
    """Test updating follow-up status."""
    # Add an email
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    # Update follow-up status
    manager.update_followup_status("test@example.com")

    db = manager.load_followup_db()
    email = db["emails"][0]
    assert email["followup_count"] == 1
    assert "last_contact" in email
    assert "next_followup" in email


def test_max_followups(manager):
    """Test that follow-ups are limited to 2."""
    # Add an email
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    # Update follow-up status twice
    manager.update_followup_status("test@example.com")
    manager.update_followup_status("test@example.com")

    # Third follow-up should not be pending
    pending = manager.get_pending_followups()
    assert len(pending) == 0


def test_default_manager():
    """Test the default manager instance."""
    assert isinstance(default_manager, FollowupManager)
    assert default_manager.db_path == Path(
        os.getenv("FOLLOWUP_DB_PATH", "followup_db.json")
    )
    assert default_manager.followup_wait_days == int(
        os.getenv("FOLLOWUP_WAIT_DAYS", "3")
    )
    assert default_manager.timezone == ZoneInfo(os.getenv("TIMEZONE", "UTC"))


def test_save_and_load_db(manager):
    """Test saving and loading the database."""
    # Add some data
    manager.track_email(
        recruiter_email="test@example.com",
        recruiter_name="Test Recruiter",
        recruiter_company="Test Corp",
        thread_id="123",
        subject="Test Subject",
    )

    # Create a new manager with the same db path
    new_manager = FollowupManager(db_path=manager.db_path)
    db = new_manager.load_followup_db()

    assert len(db["emails"]) == 1
    assert db["emails"][0]["recruiter_email"] == "test@example.com"
