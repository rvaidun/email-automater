#!/usr/bin/env python
"""Script to send follow-up emails to recruiters."""

import argparse
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
from utils.email_args import (
    EnvironmentVariables,
    add_common_email_args,
    add_followup_args,
    get_arg_or_env,
)
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


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Send follow-up emails to recruiters")
    add_common_email_args(parser)
    add_followup_args(parser)
    return parser.parse_args()


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
    args = parse_args()

    # Initialize Gmail API
    gmail_api = GmailAPI()

    # Get values from args or env vars
    followup_body_path = get_arg_or_env(
        args.followup_body_path,
        EnvironmentVariables.FOLLOWUP_BODY_PATH,
        default="followup_template.txt",
    )
    followup_subject = get_arg_or_env(
        args.followup_subject,
        EnvironmentVariables.FOLLOWUP_SUBJECT,
        default="Follow-up: $recruiter_company Application",
    )
    timezone = get_arg_or_env(
        args.timezone,
        EnvironmentVariables.TIMEZONE,
        default="America/Los_Angeles",
    )
    followup_db_path = get_arg_or_env(
        args.followup_db_path,
        EnvironmentVariables.FOLLOWUP_DB_PATH,
        default="followup_db.json",
    )

    # Initialize FollowupManager
    followup_manager = FollowupManager(
        db_path=followup_db_path,
    )

    # Load token
    token_path = Path(args.token_path)
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
    template_path = Path(followup_body_path)
    if not template_path.exists():
        logger.error("Follow-up template not found: %s", followup_body_path)
        sys.exit(1)

    template = template_path.read_text()

    # Check if scheduling is enabled
    streak_token = get_arg_or_env(
        None,
        EnvironmentVariables.STREAK_TOKEN,
    )
    should_schedule = bool(streak_token)

    if should_schedule:
        csv_path = Path(
            get_arg_or_env(
                args.schedule_csv_path,
                EnvironmentVariables.SCHEDULE_CSV_PATH,
                default="scheduler.csv",
            )
        )
        if not csv_path.exists():
            logger.error("Schedule CSV file not found: %s", csv_path)
            should_schedule = False

    if should_schedule:
        with csv_path.open("r") as file:
            csv_reader = sh.csv.DictReader(file)
            day_ranges = sh.parse_time_ranges_csv(csv_reader)

    streak_email_address = (
        get_arg_or_env(
            args.email_address,
            EnvironmentVariables.STREAK_EMAIL_ADDRESS,
        )
        or gmail_api.get_current_user()["emailAddress"]
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
            followup_subject, recruiter_company=email_data["recruiter_company"]
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
            send_time = sh.get_scheduled_send_time(day_ranges, timezone)

            if send_time is True:
                # Current time is within allowed range
                gmail_api.send_now(email_message)
                followup_manager.update_followup_status(email_data["recruiter_email"])
            elif isinstance(send_time, sh.datetime.datetime):
                draft = gmail_api.save_draft(email_message)
                config = StreakSendLaterConfig(
                    token=streak_token,
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
