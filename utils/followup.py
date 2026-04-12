# ruff: noqa: PLR0913
"""Follow-up helpers backed by the outreach state file."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from string import Template
from typing import Any

from utils.email_content import html_to_plain_text, split_inline_subject
from utils.outreach_state import OutreachStateStore
from utils.recruiter_names import recruiter_template_context

DEFAULT_TEMPLATE_PATH = Path("email2.md")
SECOND_FOLLOWUP_TEMPLATE_PATH = Path("email3.md")


def _resolved_followup_template_path(
    path: str | Path = DEFAULT_TEMPLATE_PATH,
    *,
    followup_count: int = 0,
) -> Path:
    candidate = Path(path)
    if candidate == DEFAULT_TEMPLATE_PATH and followup_count >= 1:
        return SECOND_FOLLOWUP_TEMPLATE_PATH
    return candidate


def load_template(
    path: str | Path = DEFAULT_TEMPLATE_PATH,
    *,
    followup_count: int = 0,
) -> str:
    """Load the follow-up template from disk."""
    return _resolved_followup_template_path(
        path,
        followup_count=followup_count,
    ).read_text()


def render_template(template: str, contact: dict[str, Any]) -> str:
    """Render the follow-up template for a contact."""
    return Template(template).substitute(
        **recruiter_template_context(
            recruiter_company=contact.get("company_display_name")
            or contact.get("recruiter_company")
            or contact.get("company_name")
            or "",
            recruiter_name=str(contact["name"]),
        )
    )


def create_followup_message(
    contact: dict[str, Any],
    *,
    template: str,
    subject: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> EmailMessage:
    """Build the Gmail reply message used for follow-ups."""
    message = EmailMessage()
    message["To"] = str(contact["email"])
    inline_subject, rendered_body = split_inline_subject(
        render_template(template, contact)
    )
    resolved_subject = subject or inline_subject or ""
    message["Subject"] = (
        resolved_subject
        if resolved_subject.lower().startswith("re:")
        else f"Re: {resolved_subject}"
    )
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(html_to_plain_text(rendered_body))
    message.add_alternative(rendered_body, subtype="html")
    return message


def track_email(
    recruiter_email: str,
    recruiter_name: str,
    recruiter_company: str,
    thread_id: str,
    subject: str,
    followup_count: int = 0,
    *,
    state_path: str | Path = "state/outreach_state.json",
) -> None:
    """Track a sent or drafted email in the primary state store."""
    store = OutreachStateStore(state_path)
    store.mark_contact_sent(
        email=recruiter_email,
        company_name=recruiter_company,
        name=recruiter_name,
        title="Recruiter",
        thread_id=thread_id,
        source="gmail",
    )
    if followup_count:
        record = store.contacts[recruiter_email.strip().lower()]
        record["followup_count"] = followup_count
        store.contacts[recruiter_email.strip().lower()] = record
    record = store.contacts[recruiter_email.strip().lower()]
    record["subject"] = subject
    store.contacts[recruiter_email.strip().lower()] = record
    store.save()
