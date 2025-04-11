#!/usr/bin/env python
"""Script to send follow-up emails to recruiters."""

import json
import logging
import os
import sys
from email.message import EmailMessage
from pathlib import Path
from string import Template

from dotenv import load_dotenv

import utils.schedule_helper as sh
from utils.customformatter import CustomFormatter
from utils.followup import FollowupManager
from utils.gmail import GmailAPI
from utils.streak import StreakSendLaterConfig, schedule_send_later

# Setup logging
load_dotenv()

logging.getLogger().setLevel(int(os.getenv("LOG_LEVEL", logging.INFO)))
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logging.getLogger().addHandler(handler)

logger = logging.getLogger(__name__)

# Environment variables
FOLLOWUP_BODY_PATH = os.getenv("FOLLOWUP_BODY_PATH", "followup_template.txt")
FOLLOWUP_SUBJECT = os.getenv(
    "FOLLOWUP_SUBJECT", "Follow-up: $recruiter_company Application"
)
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")
STREAK_TOKEN = os.getenv("STREAK_TOKEN")
SCHEDULE_CSV_PATH = os.getenv("SCHEDULE_CSV_PATH", "scheduler.csv")
STREAK_EMAIL_ADDRESS = os.getenv("STREAK_EMAIL_ADDRESS")
FOLLOWUP_DB_PATH = os.getenv("FOLLOWUP_DB_PATH", "followup_db.json")
FOLLOWUP_WAIT_DAYS = int(os.getenv("FOLLOWUP_WAIT_DAYS", "3"))


def process_string(s: str, **kwargs: dict) -> str:
    """Process a template string and substitute placeholders with values."""
    template = Template(s)
    return template.substitute(**kwargs)


def create_email_message(
    message_body: str,
    to_address: str,
    subject: str,
) -> EmailMessage:
    """Create an email message without attachments."""
    message = EmailMessage()
    message.set_content(message_body, subtype="html")
    message["To"] = to_address
    message["Subject"] = subject
    return message


def main() -> None:  # noqa: C901, PLR0915
    """Send follow-up emails."""
    # Initialize Gmail API
    gmail_api = GmailAPI()

    # Initialize FollowupManager
    followup_manager = FollowupManager(
        db_path=FOLLOWUP_DB_PATH,
        followup_wait_days=FOLLOWUP_WAIT_DAYS,
        timezone=TIMEZONE,
    )

    # Load token
    token_path = Path("token.json")
    if not token_path.exists():
        logger.error("No token.json file found")
        sys.exit(1)

    with token_path.open("r") as file:
        token = file.read()
        token_json = json.loads(token)
        creds = gmail_api.login(token_json)
    with token_path.open("w") as file:
        file.write(creds.to_json())

    # Get pending follow-ups
    pending_followups = followup_manager.get_pending_followups()

    if not pending_followups:
        logger.info("No pending follow-ups found")
        return

    logger.info("Found %d pending follow-ups", len(pending_followups))

    # Load follow-up template
    template_path = Path(FOLLOWUP_BODY_PATH)
    if not template_path.exists():
        logger.error("Follow-up template not found: %s", FOLLOWUP_BODY_PATH)
        sys.exit(1)

    template = template_path.read_text()

    # Check if scheduling is enabled
    should_schedule = bool(STREAK_TOKEN)
    if should_schedule:
        csv_path = Path(SCHEDULE_CSV_PATH)
        if not csv_path.exists():
            logger.error("Schedule CSV file not found: %s", SCHEDULE_CSV_PATH)
            should_schedule = False

    if should_schedule:
        with csv_path.open("r") as file:
            csv_reader = sh.csv.DictReader(file)
            day_ranges = sh.parse_time_ranges_csv(csv_reader)

    streak_email_address = (
        STREAK_EMAIL_ADDRESS or gmail_api.get_current_user()["emailAddress"]
    )

    # Process each follow-up
    for email_data in pending_followups:
        # Create follow-up email
        email_contents = process_string(
            template,
            recruiter_name=email_data["recruiter_name"],
            recruiter_company=email_data["recruiter_company"],
        )

        subject = process_string(
            FOLLOWUP_SUBJECT, recruiter_company=email_data["recruiter_company"]
        )

        email_message = create_email_message(
            email_contents,
            email_data["recruiter_email"],
            subject,
        )

        logger.info(
            "Sending follow-up to: %s, Company: %s, Follow-up #%d",
            email_data["recruiter_email"],
            email_data["recruiter_company"],
            email_data["followup_count"] + 1,
        )

        # Handle email sending or scheduling
        if not should_schedule:
            logger.info("Draft saved")
            draft = gmail_api.save_draft(email_message)
            followup_manager.update_followup_status(email_data["recruiter_email"])
        else:
            send_time = sh.get_scheduled_send_time(day_ranges, TIMEZONE)

            if send_time is True:
                # Current time is within allowed range
                gmail_api.send_now(email_message)
                followup_manager.update_followup_status(email_data["recruiter_email"])
            elif isinstance(send_time, sh.datetime.datetime):
                draft = gmail_api.save_draft(email_message)
                config = StreakSendLaterConfig(
                    token=STREAK_TOKEN,
                    to_address=email_data["recruiter_email"],
                    subject=subject,
                    thread_id=draft["message"]["threadId"],
                    draft_id=draft["id"],
                    send_date=send_time,
                    is_tracked=True,
                    email_address=streak_email_address,
                )
                schedule_send_later(config)
                followup_manager.update_followup_status(email_data["recruiter_email"])
            else:
                logger.error("Failed to schedule follow-up email")


if __name__ == "__main__":
    main()
