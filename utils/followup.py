"""Utility functions for managing email follow-ups."""

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class FollowupManager:
    """Manages email follow-ups with configurable settings."""

    def __init__(
        self,
        db_path: str = "followup_db.json",
    ) -> None:
        """
        Initialize the FollowupManager.

        Args:
            db_path: Path to the database file

        """
        self.db_path = Path(db_path)

    def load_followup_db(self) -> dict[str, list]:
        """Load the follow-up database from disk."""
        logger.debug("Loading follow-up database from %s", self.db_path)

        if not self.db_path.exists():
            logger.debug("Database file does not exist, creating empty database")
            return {"emails": []}

        with self.db_path.open("r") as f:
            data = json.load(f)
            logger.debug(
                "Loaded database with %d email entries", len(data.get("emails", []))
            )
            return data

    def save_followup_db(self, db: dict) -> None:
        """Save the follow-up database to disk."""
        logger.debug(
            "Saving follow-up database with %d email entries", len(db.get("emails", []))
        )
        with self.db_path.open("w") as f:
            json.dump(db, f, indent=4)
        logger.debug("Database saved successfully")

    def track_email(  # noqa: PLR0913
        self,
        recruiter_email: str,
        recruiter_name: str,
        recruiter_company: str,
        thread_id: str,
        subject: str,
        followup_wait_days: int = 3,
        max_followups: int = 2,
        timezone: str = "UTC",
    ) -> None:
        """
        Add a sent email to the tracking database.

        Args:
            recruiter_email: Email address of the recipient
            recruiter_name: Name of the recipient
            recruiter_company: Company of the recipient
            thread_id: Gmail thread ID
            subject: Email subject
            followup_wait_days: Number of days to wait before the next follow-up
            max_followups: Maximum number of follow-ups allowed
            timezone: Timezone for scheduling follow-ups

        """
        db = self.load_followup_db()

        # Check if this email already exists
        for email in db["emails"]:
            if email["recruiter_email"] == recruiter_email:
                # Update the existing entry
                email["thread_id"] = thread_id
                email["last_contact"] = datetime.datetime.now(
                    tz=self.timezone
                ).isoformat()
                email["followup_count"] = 0
                self.save_followup_db(db)
                return

        # Add new email entry
        db["emails"].append(
            {
                "recruiter_email": recruiter_email,
                "recruiter_name": recruiter_name,
                "recruiter_company": recruiter_company,
                "thread_id": thread_id,
                "subject": subject,
                "initial_contact": datetime.datetime.now(tz=self.timezone).isoformat(),
                "last_contact": datetime.datetime.now(tz=self.timezone).isoformat(),
                "followup_count": 0,
                "next_followup": (
                    datetime.datetime.now(tz=self.timezone)
                    + datetime.timedelta(days=followup_wait_days)
                ).isoformat(),
                "max_followups": max_followups,
                "followup_wait_days": followup_wait_days,
                "timezone": timezone,
            }
        )

        self.save_followup_db(db)
        logger.info("Tracked email to %s for follow-up", recruiter_email)

    def get_pending_followups(self) -> list[dict[str, Any]]:
        """
        Get all emails that are due for a follow-up.

        Returns:
            List of email entries that need follow-up

        """
        db = self.load_followup_db()
        now = datetime.datetime.now(tz=self.timezone).isoformat()

        return [
            email
            for email in db["emails"]
            if email.get("next_followup")
            and email["next_followup"] <= now
            and email["followup_count"] < 2  # Limit to 2 follow-ups  # noqa: PLR2004
        ]

    def update_followup_status(
        self,
        recruiter_email: str,
    ) -> None:
        """
        Update the follow-up status for an email.

        Args:
            recruiter_email: Email address to update
            increment_count: Whether to increment the follow-up count

        """
        db = self.load_followup_db()

        for email in db["emails"]:
            if email["recruiter_email"] == recruiter_email:
                email["followup_count"] += 1
                email["last_contact"] = datetime.datetime.now(
                    tz=self.timezone
                ).isoformat()
                email["next_followup"] = (
                    datetime.datetime.now(tz=self.timezone)
                    + datetime.timedelta(days=self.followup_wait_days)
                ).isoformat()

                self.save_followup_db(db)
                return

        logger.warning("Email to %s not found in tracking database", recruiter_email)


# Create a default instance for backward compatibility
default_manager = FollowupManager(
    db_path=os.getenv("FOLLOWUP_DB_PATH", "followup_db.json"),
    followup_wait_days=int(os.getenv("FOLLOWUP_WAIT_DAYS", "3")),
    timezone=os.getenv("TIMEZONE", "UTC"),
)

# Expose the default instance's methods as module-level functions
load_followup_db = default_manager.load_followup_db
save_followup_db = default_manager.save_followup_db
track_email = default_manager.track_email
get_pending_followups = default_manager.get_pending_followups
update_followup_status = default_manager.update_followup_status
