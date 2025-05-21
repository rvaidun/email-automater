#!/usr/bin/env python
"""Automates sending emails to recruiters."""

import argparse
import csv
import datetime
import json
import logging
import os.path
import sys
from email.message import EmailMessage
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import utils.schedule_helper as sh
from utils.customformatter import CustomFormatter
from utils.email_args import (
    EnvironmentVariables,
    add_common_email_args,
    add_initial_email_args,
    get_arg_or_env,
    get_bool_arg_or_env,
)
from utils.followup import FollowupManager
from utils.gmail import GmailAPI
from utils.streak import StreakSendLaterConfig, schedule_send_later

load_dotenv()

logging.getLogger().setLevel(int(os.getenv("LOG_LEVEL", logging.INFO)))
# set the default formatter to use CustomFormatter as the handler
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logging.getLogger().addHandler(handler)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automates sending emails to recruiters"
    )
    add_initial_email_args(parser)
    add_common_email_args(parser)
    return parser.parse_args()


def process_string(s: str, **kwargs: dict) -> str:
    """
    Process a file and substitute placeholders with values.

    filename: The name of the file to process.
    **kwargs: The key-value pairs to substitute in the file.
    For example, if the file contains the placeholder ${name},
    you can pass name='John' to substitute it with 'John'.

    Returns the processed file contents as a string.
    """
    template = Template(s)
    return template.substitute(**kwargs)


def create_email_message(
    message_body: str,
    to_address: str,
    subject: str,
    attachment: bytes | None = None,
    attachment_name: str | None = None,
) -> EmailMessage:
    """
    Create an email message.

    message_body: The body of the email message.
    to_address: The email address of the recipient.
    subject: The subject of the email message.
    attachment: The path to the attachment file, if any.

    Returns an EmailMessage object.
    """
    message = EmailMessage()

    message.set_content(message_body, subtype="html")
    if attachment:
        if attachment_name:
            message.add_attachment(
                attachment,
                maintype="application",
                subtype="octet-stream",
                filename=attachment_name,
            )
        else:
            logger.error("Attachment name not provided, skipping attachment")

    message["To"] = to_address
    message["Subject"] = subject

    return message


def schedule_send(
    timezone: str,
    csv_path: str,
    draft: dict,
    streak_token: str,
    streak_email_address: str,
) -> bool:
    """
    Schedule the email to be sent later using Streak.

    timezone: The timezone to use for scheduling.
    csv_path: The path to the CSV file containing the schedule.
    draft: The draft email object.
    streak_token: The Streak API token.
    streak_email_address: The email address to use in Streak scheduling.
    """
    if not streak_token:
        logger.error("Scheduling error: No streak token provided.")
        return False
    if not csv_path:
        logger.error("Scheduling error: No schedule csv file provided.")
        return False
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error("Scheduling Error: No schedule csv file found.")
        return False
    if not streak_email_address:
        logger.warning(
            "Scheduling warning %s not provided. Streak scheduling may not work as \
            expected",
            EnvironmentVariables.STREAK_EMAIL_ADDRESS.value,
        )
    with csv_path.open("r") as file:
        csv_reader = csv.DictReader(file)
        day_ranges = sh.parse_time_ranges_csv(csv_reader)

    send_time = sh.get_scheduled_send_time(day_ranges, timezone)
    if send_time is True:
        # current time is within allowed range
        # send time should be 10 minutes from now to allow sufficient time for user to
        # edit the draft in case of any errors.
        send_time = datetime.datetime.now(tz=ZoneInfo(timezone)) + datetime.timedelta(
            minutes=10
        )
    config = StreakSendLaterConfig(
        token=streak_token,
        to_address=args.recruiter_email,
        subject=subject,
        thread_id=draft["message"]["threadId"],
        draft_id=draft["id"],
        send_date=send_time,
        is_tracked=True,
        email_address=streak_email_address,
    )
    return schedule_send_later(config)


def save_for_followup(draft: dict) -> None:
    """
    Save the email for follow-up tracking.

    draft_or_sent: The draft or sent email object.
    """
    thread_id = draft.get("message", {}).get("threadId")
    if thread_id:
        fm = FollowupManager(
            db_path=get_arg_or_env(
                None,
                EnvironmentVariables.FOLLOWUP_DB_PATH,
                default="followup_db.json",
            ),
            followup_wait_days=int(
                get_arg_or_env(
                    None,
                    EnvironmentVariables.FOLLOWUP_WAIT_DAYS,
                    default="3",
                )
            ),
            timezone=get_arg_or_env(
                None,
                EnvironmentVariables.TIMEZONE,
                default="UTC",
            ),
        )
        fm.track_email(
            args.recruiter_email,
            args.recruiter_name,
            args.recruiter_company,
            thread_id,
            subject,
        )
        logger.info("Email tracked for follow-up")
    else:
        logger.warning("Could not track email for follow-up: No thread ID")


if __name__ == "__main__":
    args = parse_args()
    gmail_api = GmailAPI()

    # Get values from args or env vars
    subject = get_arg_or_env(
        args.subject,
        EnvironmentVariables.EMAIL_SUBJECT,
        required=True,
    )
    message_body_path = get_arg_or_env(
        args.message_body_path,
        EnvironmentVariables.MESSAGE_BODY_PATH,
        required=True,
    )
    attachment_path_string = get_arg_or_env(
        args.attachment_path,
        EnvironmentVariables.ATTACHMENT_PATH,
    )
    attachment_name = get_arg_or_env(
        args.attachment_name,
        EnvironmentVariables.ATTACHMENT_NAME,
    )

    if bool(attachment_path_string) ^ bool(attachment_name):  # XOR
        logger.error(
            "attachment_path and attachment_name must both appear if either is provided"
        )
        sys.exit(1)

    should_schedule = get_bool_arg_or_env(
        args.schedule,
        EnvironmentVariables.ENABLE_STREAK_SCHEDULING,
    )
    enable_followup = get_bool_arg_or_env(
        args.followup,
        EnvironmentVariables.ENABLE_FOLLOWUP,
    )

    # Log follow-up status
    logger.info("Auto follow-up is %s", "enabled" if enable_followup else "disabled")

    token_path = Path(args.token_path)
    attachment = (
        Path(attachment_path_string).read_bytes() if attachment_path_string else None
    )
    template = Path(message_body_path).read_text()

    if token_path.exists():
        with token_path.open("r") as file:
            token = file.read()
            token_json = json.loads(token)
            creds = gmail_api.login(token_json)
        with token_path.open("w") as file:
            file.write(creds.to_json())
    else:
        logger.error("No token.json file found")
        sys.exit(1)

    email_contents = process_string(
        template,
        recruiter_name=args.recruiter_name,
        recruiter_company=args.recruiter_company,
    )
    subject = process_string(subject, recruiter_company=args.recruiter_company)
    email_message = create_email_message(
        email_contents,
        args.recruiter_email,
        subject,
        attachment=attachment,
        attachment_name=attachment_name,
    )
    logger.info(
        "Recruiter email: %s, Recruiter Name: %s, Recruiter Company: %s",
        args.recruiter_email,
        args.recruiter_name,
        args.recruiter_company,
    )
    draft = gmail_api.save_draft(email_message)
    logger.info("Draft saved to gmail")
    if should_schedule:
        timezone = get_arg_or_env(
            args.timezone,
            EnvironmentVariables.TIMEZONE,
            default="UTC",
        )
        streak_token = get_arg_or_env(
            None,
            EnvironmentVariables.STREAK_TOKEN,
            required=True,
        )
        csv_path = get_arg_or_env(
            args.schedule_csv_path,
            EnvironmentVariables.SCHEDULE_CSV_PATH,
            required=True,
        )
        streak_email_address = (
            get_arg_or_env(
                args.email_address,
                EnvironmentVariables.STREAK_EMAIL_ADDRESS,
            )
            or gmail_api.get_current_user()["emailAddress"]
        )
        schedule_send(timezone, csv_path, draft, streak_token, streak_email_address)
    if enable_followup:
        save_for_followup(draft)
