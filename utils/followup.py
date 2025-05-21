"""Utility functions for managing email follow-ups."""

import datetime
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FollowupManager:
    """Manages email follow-ups with configurable settings."""

    def __init__(
        self,
        db_path: str = "followup.db",
    ) -> None:
        """
        Initialize the FollowupManager.

        Args:
            db_path: Path to the SQLite database file

        """
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        return conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    recruiter_email TEXT PRIMARY KEY,
                    recruiter_name TEXT NOT NULL,
                    recruiter_company TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    followup_count INTEGER NOT NULL DEFAULT 0,
                    next_followup TEXT,
                    max_followups INTEGER NOT NULL DEFAULT 2,
                    followup_wait_days INTEGER NOT NULL DEFAULT 3,
                    timezone TEXT NOT NULL DEFAULT 'UTC'
                )
            """)
            conn.commit()

    def track_email(  # noqa: PLR0913
        self,
        recruiter_email: str,
        recruiter_name: str,
        recruiter_company: str,
        thread_id: str,
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
            followup_wait_days: Number of days to wait before the next follow-up
            max_followups: Maximum number of follow-ups allowed
            timezone: Timezone for scheduling follow-ups

        """
        now = datetime.datetime.now(tz=datetime.UTC).isoformat()
        next_followup = (
            datetime.datetime.now(tz=datetime.UTC)
            + datetime.timedelta(days=followup_wait_days)
        ).isoformat()

        with self._get_connection() as conn:
            # Check if email exists
            cursor = conn.execute(
                "SELECT recruiter_email FROM emails WHERE recruiter_email = ?",
                (recruiter_email,),
            )
            if cursor.fetchone():
                # Update existing entry
                logger.warning(
                    "Email to %s already exists in tracking database,skipping",
                    recruiter_email,
                )
            else:
                # Insert new entry
                conn.execute(
                    """
                    INSERT INTO emails (
                        recruiter_email, recruiter_name, recruiter_company,
                        thread_id,
                        followup_count, next_followup, max_followups,
                        followup_wait_days, timezone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recruiter_email,
                        recruiter_name,
                        recruiter_company,
                        thread_id,
                        0,
                        next_followup,
                        max_followups,
                        followup_wait_days,
                        timezone,
                    ),
                )
            conn.commit()
        logger.info("Tracked email to %s for follow-up", recruiter_email)

    def get_pending_followups(self) -> list[dict[str, Any]]:
        """
        Get all emails that are due for a follow-up.

        Returns:
            List of email entries that need follow-up

        """
        now = datetime.datetime.now(tz=datetime.UTC).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM emails
                WHERE next_followup <= ?
                AND followup_count < max_followups
                """,
                (now,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_followup_status(
        self,
        recruiter_email: str,
    ) -> None:
        """
        Update the follow-up status for an email.

        Args:
            recruiter_email: Email address to update

        """
        with self._get_connection() as conn:
            # Get the current email's settings
            cursor = conn.execute(
                "SELECT followup_wait_days, timezone FROM emails WHERE recruiter_email = ?",
                (recruiter_email,),
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(
                    "Email to %s not found in tracking database", recruiter_email
                )
                return

            now = datetime.datetime.now(tz=datetime.UTC).isoformat()
            next_followup = (
                datetime.datetime.now(tz=datetime.UTC)
                + datetime.timedelta(days=row["followup_wait_days"])
            ).isoformat()

            cursor = conn.execute(
                """
                UPDATE emails
                SET followup_count = followup_count + 1,
                    next_followup = ?
                WHERE recruiter_email = ?
                """,
                (next_followup, recruiter_email),
            )
            if cursor.rowcount == 0:
                logger.warning(
                    "Email to %s not found in tracking database", recruiter_email
                )
            conn.commit()

    def get_email_status(self, recruiter_email: str) -> dict[str, Any] | None:
        """
        Get the current status of an email.

        Args:
            recruiter_email: Email address to look up

        Returns:
            Dictionary containing email status or None if not found

        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM emails WHERE recruiter_email = ?",
                (recruiter_email,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
