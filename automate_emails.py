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
from enum import Enum
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import utils.schedule_helper as sh
from utils.cron_setup import setup_cron_job
from utils.customformatter import CustomFormatter
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


class EnvironmentVariables(Enum):
    """Environment variables."""

    EMAIL_SUBJECT = "EMAIL_SUBJECT"
    MESSAGE_BODY_PATH = "MESSAGE_BODY_PATH"
    ATTACHMENT_PATH = "ATTACHMENT_PATH"
    ATTACHMENT_NAME = "ATTACHMENT_NAME"
    ENABLE_STREAK_SHEDULING = "ENABLE_STREAK_SCHEDULING"
    STREAK_TOKEN = "STREAK_TOKEN"  # noqa: S105
    TIMEZONE = "TIMEZONE"
    SCHEDULE_CSV_PATH = "SCHEDULE_CSV_PATH"
    STREAK_EMAIL_ADDRESS = "STREAK_EMAIL_ADDRESS"
    ENABLE_FOLLOWUP = "ENABLE_FOLLOWUP"


# If modifying these scopes, delete the file token.json.


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automates sending emails to recruiters"
    )
    parser.add_argument(
        "recruiter_company", type=str, help="The company name of the recruiter"
    )
    parser.add_argument(
        "recruiter_name", type=str, help="The full name of the recruiter"
    )

    parser.add_argument(
        "recruiter_email", type=str, help="The email address of the recruiter"
    )
    parser.add_argument(
        "-s",
        "--subject",
        type=str,
        help=f"The subject of the email message as a string template env: \
            {EnvironmentVariables.EMAIL_SUBJECT.value}",
        nargs="?",
    )
    parser.add_argument(
        "-m",
        "--message_body_path",
        type=str,
        help=f"The path to the message body template. env: \
            {EnvironmentVariables.MESSAGE_BODY_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "-ap",
        "--attachment_path",
        type=str,
        help=f"The path to the attachment file, if this is provided, attachment_name \
            must also be provided env: {EnvironmentVariables.ATTACHMENT_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "-an",
        "--attachment_name",
        type=str,
        help=f"The name of the attachment file env: \
            {EnvironmentVariables.ATTACHMENT_NAME.value}",
        nargs="?",
    )
    parser.add_argument(
        "-sch",
        "--schedule",
        help=f"Whether the email should be tracked or not. env \
            {EnvironmentVariables.ENABLE_STREAK_SHEDULING.value}. \
            If set, the streak token must be provided via env variable \
            {EnvironmentVariables.STREAK_TOKEN.value}",
        action="store_true",
    )
    parser.add_argument(
        "-scsv",
        "--schedule_csv_path",
        type=bool,
        help=f"CSV to use for scheduling the emails \
            env: {EnvironmentVariables.SCHEDULE_CSV_PATH.value}. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "-tz",
        "--timezone",
        type=str,
        help=f"The timezone to use for scheduling emails (America/New_York) env:\
            {EnvironmentVariables.TIMEZONE.value} \
            This is used to determine the time range so it should be the recepeint's \
            timezone. ",
        nargs="?",
    )
    parser.add_argument(
        "-e",
        "--email_address",
        type=str,
        help=f"The email address to use in streak scheduling emails env: \
            {EnvironmentVariables.STREAK_EMAIL_ADDRESS.value} \
            If not provided, the email address of the authenticated user will be used. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "-t",
        "--token_path",
        type=str,
        help="The path to the token.json file. Defaults to token.json",
        nargs="?",
        default="token.json",
    )
    parser.add_argument(
        "-f",
        "--followup",
        help=f"Whether to enable automatic follow-up for this email. env: \
            {EnvironmentVariables.ENABLE_FOLLOWUP.value}",
        action="store_true",
    )

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
    draft: str,
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
    csv_reader = csv.DictReader(file)
    day_ranges = sh.parse_time_ranges_csv(csv_reader)

    send_time = sh.get_scheduled_send_time(day_ranges, timezone)
    if send_time is True:
        # current time is within allowed range
        # send time should be 10 minutes from now
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


def save_for_followup(fm: FollowupManager, draft_or_sent: dict) -> None:
    """
    Save the email for follow-up tracking.

    draft_or_sent: The draft or sent email object.
    """


if __name__ == "__main__":
    args = parse_args()
    gmail_api = GmailAPI()
    subject = args.subject or os.getenv(EnvironmentVariables.EMAIL_SUBJECT.value)
    message_body_path = args.message_body_path or os.getenv(
        EnvironmentVariables.MESSAGE_BODY_PATH.value
    )
    attachment_path_string = args.attachment_path or os.getenv(
        EnvironmentVariables.ATTACHMENT_PATH.value
    )
    attachment_name = args.attachment_name or os.getenv(
        EnvironmentVariables.ATTACHMENT_NAME.value
    )
    if bool(attachment_path_string) ^ bool(attachment_name):  # XOR
        logger.error(
            "attachment_path and attachment_name must both appear if either is provided"
        )
        sys.exit(1)
    should_schedule = args.schedule or os.getenv(
        EnvironmentVariables.ENABLE_STREAK_SHEDULING.value
    )
    enable_followup = args.enable_followup or os.getenv(
        EnvironmentVariables.ENABLE_FOLLOWUP.value
    )
    if isinstance(enable_followup, str):
        if enable_followup.lower() == "true":
            enable_followup = True
        elif enable_followup.lower() == "false":
            enable_followup = False
        else:
            logger.warning(
                "Invalid value for ENABLE_FOLLOWUP. Must be 'true' or 'false'. \
                Defaulting to false"
            )
            enable_followup = False

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
        timezone = args.timezone or os.getenv(EnvironmentVariables.TIMEZONE.value)
        streak_token = os.getenv(EnvironmentVariables.STREAK_TOKEN.value)
        csv_path = args.schedule_csv_path or os.getenv(
            EnvironmentVariables.SCHEDULE_CSV_PATH.value
        )
        streak_email_address = (
            args.email_address
            or os.getenv(EnvironmentVariables.STREAK_EMAIL_ADDRESS.value)
            or gmail_api.get_current_user()["emailAddress"]
        )
        schedule_send(timezone, csv_path, draft, streak_token, streak_email_address)
    if enable_followup:
        thread_id = draft.get("message", {}).get("threadId")
        if thread_id:
            fm = FollowupManager(
                db_path=os.getenv("FOLLOWUP_DB_PATH", "followup_db.json"),
                followup_wait_days=int(os.getenv("FOLLOWUP_WAIT_DAYS", "3")),
                timezone=timezone,
            )
            fm.track_email(
                args.recruiter_email,
                args.recruiter_name,
                args.recruiter_company,
                thread_id,
                subject,
            )

            # Set up automatic cron job for follow-ups if enabled
            try:
                if setup_cron_job():
                    logger.info("Automatic follow-up cron job set up successfully")
                else:
                    logger.warning("Could not set up automatic follow-up cron job")
            except Exception as e:  # noqa: BLE001
                logger.warning("Error setting up cron job: %s", e)
        else:
            logger.warning("Could not track email for follow-up: No thread ID")
