#!/usr/bin/env python
"""Automates sending emails to recruiters."""

import argparse
import datetime
import json
import logging
import os.path
import sys
from email.message import EmailMessage
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
        "--template_path",
        type=str,
        help="The path to the attachment file",
        default=os.getenv("MESSAGE_BODY_PATH"),
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
    recruiter = args.recruiter_name
    recruiter_name = args.recruiter_name
    recruiter_company = args.recruiter_company
    recruiter_email = args.recruiter_email
    subject = os.getenv("EMAIL_SUBJECT")
    attachment_path_string = os.getenv("ATTACHMENT_PATH")
    attachment_name = os.getenv("ATTACHMENT_NAME")
    streak_token = os.getenv("STREAK_TOKEN")

    token_path = Path("token.json")
    attachment = (
        Path(attachment_path_string).read_bytes(
        ) if attachment_path_string else None
    )
    template = Path(args.template_path).read_text()

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
        template, recruiter_name=recruiter_name, recruiter_company=recruiter_company
    )
    subject = process_string(subject, recruiter_company=recruiter_company)
    email_message = create_email_message(
        email_contents,
        recruiter_email,
        subject,
        attachment=attachment,
        attachment_name=attachment_name,
    )

    draft = gmail_api.save_draft(email_message)
    config = StreakSendLaterConfig()
    config.token = streak_token
    config.to_address = recruiter_email
    config.subject = subject
    config.thread_id = draft["message"]["threadId"]
    config.draft_id = draft["id"]
    # if the time is now between 00:00 AM and 9:50 AM, schedule the email to be sent at
    # a random time between 10:00 AM and 11:00 AM

    # if the time is between 9:50 AM and 1:50 PM, schedule the email to be sent at a
    # random time between 2:00 and 2:30 PM

    # if the time is between 2:30 PM and 23:59 PM on MTWT, schedule the email to be
    # sent at a random time between tomorrow 10:00 AM and 11:00 AM

    # if the time is between 2:30 PM and 23:59 PM on F, schedule the email to be sent
    # or any time during the weekend schedule the email to be sent at a random time
    # between Monday 10:00 AM and 11:00 AM

    # all times are in the timezone of Pacific Time
    send_time = sh.get_scheduled_send_time()

    if send_time is True:
        gmail_api.send_now(email_message)
    elif isinstance(send_time, datetime.datetime):
        config.send_date = send_time
        config.is_tracked = True
        schedule_send_later(config)
