#!/usr/bin/env python
"""Automates sending emails to recruiters."""

import argparse
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
from utils.gmail import GmailAPI
from utils.streak import StreakSendLaterConfig, schedule_send_later

load_dotenv()
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())
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
        help=f"The path to the attachment file env: \
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
        type=bool,
        help=f"Whether the email should be tracked or not. env \
            {EnvironmentVariables.ENABLE_STREAK_SHEDULING} \n \
            If set, the streak token must be provided env: \
            {EnvironmentVariables.STREAK_TOKEN.value}",
        nargs=0,
        default=False,
    )
    parser.add_argument(
        "--timezone",
        type=str,
        help=f"The timezone to use for scheduling emails env: \n \
            {EnvironmentVariables.TIMEZONE.value} \
            Note: the argument tracked needs to be passed for this to be used",
        default="UTC",
        nargs="?",
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
    should_schedule = args.tracked or os.getenv(
        EnvironmentVariables.ENABLE_STREAK_SHEDULING.value
    )
    timezone = args.timezone or os.getenv(EnvironmentVariables.TIMEZONE.value)
    streak_token = os.getenv(EnvironmentVariables.STREAK_TOKEN.value)

    token_path = Path("token.json")
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

    if not should_schedule:
        draft = gmail_api.save_draft(email_message)
        sys.exit(0)

    # below this point the email is scheduled
    send_time = sh.get_scheduled_send_time()

    if send_time is True:
        gmail_api.send_now(email_message)  # current time is within allowed range
    elif isinstance(send_time, datetime.datetime):
        draft = gmail_api.save_draft(email_message)
        config = StreakSendLaterConfig(
            token=streak_token,
            to_address=args.recruiter_email,
            subject=subject,
            thread_id=draft["message"]["threadId"],
            draft_id=draft["id"],
            send_date=send_time,
            is_tracked=True,
        )
        schedule_send_later(config)
    else:
        logger.error("Failed to schedule email")
        sys.exit(1)
