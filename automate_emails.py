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

from dotenv import load_dotenv

import utils.schedule_helper as sh
from utils.cron_setup import setup_cron_job
from utils.customformatter import CustomFormatter
from utils.followup import track_email
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
        "--subject",
        type=str,
        help=f"The subject of the email message as a string template env: \
            {EnvironmentVariables.EMAIL_SUBJECT.value}",
        nargs="?",
    )
    parser.add_argument(
        "--message_body_path",
        type=str,
        help=f"The path to the message body template. env: \
            {EnvironmentVariables.MESSAGE_BODY_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "--attachment_path",
        type=str,
        help=f"The path to the attachment file, if this is provided, attachment_name \
            must also be provided env: {EnvironmentVariables.ATTACHMENT_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "--attachment_name",
        type=str,
        help=f"The name of the attachment file env: \
            {EnvironmentVariables.ATTACHMENT_NAME.value}",
        nargs="?",
    )
    parser.add_argument(
        "--schedule",
        help=f"Whether the email should be tracked or not. env \
            {EnvironmentVariables.ENABLE_STREAK_SHEDULING.value}. \
            If set, the streak token must be provided via env variable \
            {EnvironmentVariables.STREAK_TOKEN.value}",
        action="store_true",
    )
    parser.add_argument(
        "--schedule_csv_path",
        type=bool,
        help=f"CSV to use for scheduling the emails \
            env: {EnvironmentVariables.SCHEDULE_CSV_PATH.value}. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "--timezone",
        "-tz",
        type=str,
        help=f"The timezone to use for scheduling emails (America/New_York) env:\
            {EnvironmentVariables.TIMEZONE.value} \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "--email_address",
        type=str,
        help=f"The email address to use in streak scheduling emails env: \
            {EnvironmentVariables.STREAK_EMAIL_ADDRESS.value} \
            If not provided, the email address of the authenticated user will be used. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "--token_path",
        type=str,
        help="The path to the token.json file. Defaults to token.json",
        nargs="?",
        default="token.json",
    )
    parser.add_argument(
        "--enable_followup",
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
    # Always enable follow-up by default, but still allow disabling via env var if set to "False"
    enable_followup_env = os.getenv(EnvironmentVariables.ENABLE_FOLLOWUP.value)
    enable_followup = True
    if enable_followup_env and enable_followup_env.lower() == "false":
        enable_followup = False
    # Override with command line argument if provided
    if args.enable_followup:
        enable_followup = True

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

    def save_for_followup(draft_or_sent):
        if enable_followup:
            thread_id = draft_or_sent.get("message", {}).get("threadId") or draft_or_sent.get("threadId")
            if thread_id:
                logger.info("Tracking email for follow-up")
                track_email(
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
                except Exception as e:
                    logger.warning(f"Error setting up cron job: {e}")
            else:
                logger.warning("Could not track email for follow-up: No thread ID")

    if not should_schedule:
        logger.info("Draft saved")
        draft = gmail_api.save_draft(email_message)
        save_for_followup(draft)
        sys.exit(0)

    # below this point the email is scheduled
    timezone = args.timezone or os.getenv(EnvironmentVariables.TIMEZONE.value)
    streak_token = os.getenv(EnvironmentVariables.STREAK_TOKEN.value)
    if not streak_token:
        draft = gmail_api.save_draft(email_message)
        save_for_followup(draft)
        logger.error(
            "Scheduling error: No streak token provided. Only adding email to drafts"
        )
        sys.exit(0)
    csv_path = args.schedule_csv_path or os.getenv(
        EnvironmentVariables.SCHEDULE_CSV_PATH.value
    )
    csv_path = Path(csv_path)
    if not csv_path.exists():
        draft = gmail_api.save_draft(email_message)
        save_for_followup(draft)
        logger.error(
            "Scheduling Error: No schedule csv file found. Only adding email to drafts"
        )
        sys.exit(1)
    streak_email_address = (
        args.email_address
        or os.getenv(EnvironmentVariables.STREAK_EMAIL_ADDRESS.value)
        or gmail_api.get_current_user()["emailAddress"]
    )
    if not streak_email_address:
        draft = gmail_api.save_draft(email_message)
        save_for_followup(draft)
        logger.warning(
            "%s not provided. Streak scheduling may not work as expected",
            EnvironmentVariables.STREAK_EMAIL_ADDRESS.value,
        )
        sys.exit(1)

    with csv_path.open("r") as file:
        csv_reader = csv.DictReader(file)
        day_ranges = sh.parse_time_ranges_csv(csv_reader)

    send_time = sh.get_scheduled_send_time(day_ranges, timezone)

    if send_time is True:
        sent = gmail_api.send_now(email_message)  # current time is within allowed range
        save_for_followup(sent)
    elif isinstance(send_time, datetime.datetime):
        draft = gmail_api.save_draft(email_message)
        save_for_followup(draft)
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
        schedule_send_later(config)
    else:
        logger.error("Failed to schedule email")
        sys.exit(1)
