#!/usr/bin/env python
"""Automates sending emails to recruiters."""
import argparse
import json
import logging
import os.path
import sys
from email.message import EmailMessage
from pathlib import Path
from string import Template

from dotenv import load_dotenv

from utils.gmail import GmailAPI

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


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


def create_email_message(message_body: str, to_address: str, subject: str,
                         attachment: bytes | None = None,
                         attachment_name: str | None = None) -> EmailMessage:
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
            message.add_attachment(attachment, maintype="application",
                                   subtype="octet-stream", filename=attachment_name)
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
    attachment = os.getenv("ATTACHMENT_PATH")
    if Path.exists("token.json"):
        with Path.open("token.json", "rw") as file:
            token = file.read()
            token_json = json.loads(token)
            creds = gmail_api.login(token_json)
            file.write(creds.to_json())
    else:
        logger.error("No token.json file found")
        sys.exit(1)
    with Path.open(args.template_path, "r") as file:
        template = file.read()

    email_contents = process_string(
        template, recruiter_name=recruiter_name, recruiter_company=recruiter_company
    )
    subject = process_string(subject, recruiter_company=recruiter_company)
    email_message = create_email_message(
        email_contents, recruiter_email, subject, attachment=attachment
    )
    gmail_api.save_draft(email_message)
