# ruff: noqa: PLR0913
"""Automate a single recruiter outreach email."""

from __future__ import annotations

import argparse
import json
import os
import sys
from email.message import EmailMessage
from pathlib import Path
from string import Template
from typing import Any

from dotenv import load_dotenv

from utils.email_content import html_to_plain_text, split_inline_subject
from utils.followup import track_email
from utils.gmail import GmailAPI
from utils.logging_setup import configure_logger
from utils.recruiter_names import recruiter_template_context

load_dotenv()

logger = configure_logger(__name__)

DEFAULT_TOKEN_PATH = Path("token.json")
DEFAULT_CREDS_PATH = Path("credentials.json")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Automates sending emails to recruiters"
    )
    parser.add_argument("recruiter_company", type=str, help="The company name")
    parser.add_argument("recruiter_name", type=str, help="The recruiter name")
    parser.add_argument("recruiter_email", type=str, help="The recruiter email")
    parser.add_argument("-s", "--subject", type=str, nargs="?", help="Subject template")
    parser.add_argument(
        "-m",
        "--message_body_path",
        type=str,
        nargs="?",
        help="Path to the HTML template",
    )
    parser.add_argument(
        "-ap",
        "--attachment_path",
        type=str,
        nargs="?",
        help="Attachment path",
    )
    parser.add_argument(
        "-an",
        "--attachment_name",
        type=str,
        nargs="?",
        help="Attachment filename",
    )
    parser.add_argument(
        "-tz",
        "--timezone",
        type=str,
        nargs="?",
        help="Scheduling timezone",
    )
    parser.add_argument(
        "-t",
        "--token_path",
        type=str,
        nargs="?",
        default=str(DEFAULT_TOKEN_PATH),
        help="Path to token.json",
    )
    parser.add_argument(
        "-c",
        "--creds_path",
        type=str,
        nargs="?",
        default=str(DEFAULT_CREDS_PATH),
        help="Path to credentials.json",
    )
    parser.add_argument(
        "--enable_followup",
        action="store_true",
        help="Track the thread for automatic follow-up",
    )
    return parser.parse_args()


def process_string(s: str, **kwargs: dict[str, Any]) -> str:
    """Substitute a Python template string."""
    return Template(s).substitute(**kwargs)


def create_email_message(
    message_body: str,
    to_address: str,
    subject: str,
    attachment: bytes | None = None,
    attachment_name: str | None = None,
) -> EmailMessage:
    """Create a multipart email message with plain-text fallback."""
    message = EmailMessage()
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(html_to_plain_text(message_body))
    message.add_alternative(message_body, subtype="html")

    if attachment and attachment_name:
        message.add_attachment(
            attachment,
            maintype="application",
            subtype="octet-stream",
            filename=attachment_name,
        )
    return message


def load_authenticated_gmail(
    *,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
    creds_path: str | Path = DEFAULT_CREDS_PATH,
) -> tuple[GmailAPI, Any]:
    """Log into Gmail and refresh the token if needed."""
    gmail_api = GmailAPI()
    token_path = Path(token_path)
    creds_path = Path(creds_path)

    if token_path.exists():
        token = json.loads(token_path.read_text())
        creds = gmail_api.login(token)
        token_path.write_text(creds.to_json())
        return gmail_api, creds

    if not creds_path.exists():
        msg = f"Missing credentials file: {creds_path}"
        raise FileNotFoundError(msg)

    creds = gmail_api.login(token=None, credentials_path=str(creds_path))
    token_path.write_text(creds.to_json())
    return gmail_api, creds


def send_recruiter_email(
    *,
    recruiter_company: str,
    recruiter_name: str,
    recruiter_email: str,
    subject_template: str | None,
    message_body_path: str | Path,
    attachment_path: str | Path | None = None,
    attachment_name: str | None = None,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
    creds_path: str | Path = DEFAULT_CREDS_PATH,
    enable_followup: bool = False,
) -> dict[str, Any] | bool:
    """Send a recruiter email immediately."""
    gmail_api, _ = load_authenticated_gmail(
        token_path=token_path,
        creds_path=creds_path,
    )
    template_context = recruiter_template_context(
        recruiter_company=recruiter_company,
        recruiter_name=recruiter_name,
    )
    template = Path(message_body_path).read_text()
    email_contents = process_string(
        template,
        **template_context,
    )
    inline_subject, cleaned_email_contents = split_inline_subject(email_contents)
    subject = inline_subject or (
        process_string(subject_template, **template_context) if subject_template else ""
    )
    if not subject:
        msg = "Email subject is required via template Subject line or EMAIL_SUBJECT"
        raise ValueError(msg)
    attachment = Path(attachment_path).read_bytes() if attachment_path else None
    message = create_email_message(
        cleaned_email_contents,
        recruiter_email,
        subject,
        attachment=attachment,
        attachment_name=attachment_name,
    )

    sent = gmail_api.send_now(message)
    if sent and enable_followup:
        track_email(
            recruiter_email,
            recruiter_name,
            recruiter_company,
            sent["threadId"],
            subject,
        )
    return sent


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    subject = args.subject or os.getenv("EMAIL_SUBJECT")
    message_body_path = args.message_body_path or os.getenv("MESSAGE_BODY_PATH")
    attachment_path = args.attachment_path or os.getenv("ATTACHMENT_PATH")
    attachment_name = args.attachment_name or os.getenv("ATTACHMENT_NAME")

    if not message_body_path:
        logger.error("MESSAGE_BODY_PATH is required")
        return 1
    if bool(attachment_path) ^ bool(attachment_name):
        logger.error("attachment_path and attachment_name must both be provided")
        return 1

    try:
        result = send_recruiter_email(
            recruiter_company=args.recruiter_company,
            recruiter_name=args.recruiter_name,
            recruiter_email=args.recruiter_email,
            subject_template=subject,
            message_body_path=message_body_path,
            attachment_path=attachment_path,
            attachment_name=attachment_name,
            token_path=args.token_path,
            creds_path=args.creds_path,
            enable_followup=args.enable_followup
            or os.getenv("ENABLE_FOLLOWUP", "").lower() == "true",
        )
    except (FileNotFoundError, ValueError):
        logger.exception("Email preparation failed")
        return 1

    if not result:
        logger.error("Email send failed")
        return 1

    logger.info("Email prepared successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
