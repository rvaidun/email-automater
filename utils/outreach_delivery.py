"""Initial outreach delivery helpers used by the daily pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from automate_emails import (
    create_email_message,
    load_authenticated_gmail,
    process_string,
)
from utils.email_content import split_inline_subject
from utils.logging_setup import configure_logger
from utils.recruiter_names import recruiter_template_context
from utils.schedule_helper import paced_send_times
from utils.send_window import within_send_window

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from utils.outreach_state import OutreachStateStore

logger = configure_logger(__name__)

DEFAULT_SUBJECT_TEMPLATE = "Software Engineer - $recruiter_company"
DEFAULT_MESSAGE_TEMPLATE = "email1.md"
DEFAULT_ATTACHMENT_PATH = "resume.pdf"
DEFAULT_ATTACHMENT_NAME = "Candidate_Resume.pdf"


def render_initial_email(
    *,
    recruiter_company: str,
    recruiter_name: str,
    recruiter_email: str,
) -> tuple[str, Any]:
    """Render the initial recruiter email using the existing template flow."""
    subject_template = os.getenv("EMAIL_SUBJECT", DEFAULT_SUBJECT_TEMPLATE)
    message_template_path = Path(
        os.getenv("MESSAGE_BODY_PATH", DEFAULT_MESSAGE_TEMPLATE)
    )
    attachment_path = Path(os.getenv("ATTACHMENT_PATH", DEFAULT_ATTACHMENT_PATH))
    attachment_name = os.getenv("ATTACHMENT_NAME", DEFAULT_ATTACHMENT_NAME)

    template_context = recruiter_template_context(
        recruiter_company=recruiter_company,
        recruiter_name=recruiter_name,
    )
    rendered_body = process_string(
        message_template_path.read_text(),
        **template_context,
    )
    inline_subject, body = split_inline_subject(rendered_body)
    subject = inline_subject or process_string(subject_template, **template_context)
    if recruiter_company and recruiter_company not in subject:
        cleaned_subject = subject.strip()
        if not cleaned_subject or cleaned_subject.endswith("-"):
            subject = f"{cleaned_subject} {recruiter_company}".strip()
    attachment = attachment_path.read_bytes() if attachment_path.exists() else None
    message = create_email_message(
        body,
        recruiter_email,
        subject,
        attachment=attachment,
        attachment_name=attachment_name if attachment else None,
    )
    return subject, message


def queue_new_outreach(  # noqa: PLR0913
    *,
    contacts: list[dict[str, Any]],
    state: OutreachStateStore,
    now: datetime,
    token_path: str,
    creds_path: str,
    dry_run: bool,
    is_outreach_day: bool,
    send_window_timezone: str,
    allowed_send_weekdays: set[int],
    local_send_min_spacing_minutes: int,
    now_provider: Callable[[], datetime],
    sleep_until: Callable[[datetime], None],
    schedule_csv_path: str | None = None,
    gmail_loader: Callable[..., tuple[Any, Any]] | None = None,
    email_renderer: Callable[..., tuple[str, Any]] | None = None,
) -> tuple[int, str | None]:
    """Send the day's new outreach emails using the current local pacing flow."""
    gmail_loader = gmail_loader or load_authenticated_gmail
    email_renderer = email_renderer or render_initial_email

    if not contacts or not is_outreach_day:
        return 0, None
    if dry_run:
        return len(contacts), None
    if not within_send_window(
        now,
        timezone=send_window_timezone,
        allowed_weekdays=allowed_send_weekdays,
        schedule_csv_path=schedule_csv_path,
    ):
        return 0, "Outside the active send window for new outreach"

    gmail_api, _ = gmail_loader(
        token_path=token_path,
        creds_path=creds_path,
    )

    send_times = paced_send_times(
        len(contacts),
        now=now,
        timezone=send_window_timezone,
        allowed_weekdays=allowed_send_weekdays,
        minimum_spacing_minutes=local_send_min_spacing_minutes,
        schedule_csv_path=schedule_csv_path,
    )
    if len(send_times) < len(contacts):
        logger.info(
            "Deferring %s new outreach email(s) to a later run to keep at least "
            "%s minutes between local sends",
            len(contacts) - len(send_times),
            local_send_min_spacing_minutes,
        )
    logger.info(
        "Pacing %s Gmail sends locally across %s business hours",
        len(send_times),
        send_window_timezone,
    )
    sent = 0
    for contact, send_time in zip(contacts, send_times, strict=False):
        sleep_until(send_time)
        subject, message = email_renderer(
            recruiter_company=str(contact["company_display_name"]),
            recruiter_name=str(contact["name"]),
            recruiter_email=str(contact["email"]),
        )
        delivered = gmail_api.send_now(message)
        if not delivered:
            logger.warning("Failed to send %s immediately", contact["email"])
            continue
        record = state.mark_contact_sent(
            email=str(contact["email"]),
            company_name=str(contact["company_display_name"]),
            name=str(contact["name"]),
            title=str(contact["title"]),
            thread_id=str(delivered["threadId"]),
            source="apollo",
            sent_at=now_provider(),
            actioned_at=now,
        )
        record["subject"] = subject
        state.contacts[str(contact["email"]).strip().lower()] = record
        sent += 1

    return sent, None
