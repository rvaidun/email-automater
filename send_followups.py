# ruff: noqa: C901, PLR0912, PLR0913, PLR0915
"""Send due recruiter follow-ups as true Gmail thread replies."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from automate_emails import load_authenticated_gmail
from utils.followup import create_followup_message, load_template
from utils.logging_setup import configure_logger
from utils.outreach_state import MAX_FOLLOWUPS, OutreachStateStore
from utils.reply_detection import detect_thread_stop, headers_to_dict
from utils.schedule_helper import paced_send_times
from utils.send_window import (
    env_spacing_minutes,
    env_timezone,
    parse_allowed_weekdays,
    within_send_window,
)
from utils.send_window import (
    sleep_until as _sleep_until,
)

load_dotenv()

logger = configure_logger(__name__)

DEFAULT_STATE_PATH = "state/outreach_state.json"
DEFAULT_GMAIL_STATE_PATH = "token.json"
DEFAULT_CREDS_PATH = "credentials.json"
DEFAULT_TEMPLATE_PATH = "email2.md"
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_SEND_WINDOW_TIMEZONE = "America/New_York"
DEFAULT_FOLLOWUP_MIN_SPACING_MINUTES = 15
DEFAULT_FOLLOWUP_WEEKDAYS = "0,1,2,3,4"


def _now() -> datetime:
    """Return the current localized timestamp."""
    return datetime.now(ZoneInfo(os.getenv("TIMEZONE", DEFAULT_TIMEZONE)))


def _followup_daily_limit() -> int | None:
    raw_limit = os.getenv("FOLLOWUP_DAILY_LIMIT")
    if raw_limit is None or not raw_limit.strip():
        return None
    parsed_limit = int(raw_limit)
    return None if parsed_limit <= 0 else parsed_limit


def _followup_send_window_timezone() -> str:
    """Return the timezone used for paced follow-up sends."""
    return env_timezone(
        "FOLLOWUP_SEND_WINDOW_TIMEZONE",
        "SEND_WINDOW_TIMEZONE",
        "TIMEZONE",
        default=DEFAULT_SEND_WINDOW_TIMEZONE,
    )


def _followup_min_spacing_minutes() -> int:
    """Return the minimum gap between follow-up sends."""
    return env_spacing_minutes(
        "FOLLOWUP_MIN_SPACING_MINUTES",
        default=DEFAULT_FOLLOWUP_MIN_SPACING_MINUTES,
    )


def _allowed_followup_weekdays() -> set[int]:
    """Return weekdays allowed for follow-up sends."""
    return parse_allowed_weekdays(
        os.getenv(
            "FOLLOWUP_WEEKDAYS",
            os.getenv(
                "SEND_WEEKDAYS",
                os.getenv("OUTREACH_WEEKDAYS", DEFAULT_FOLLOWUP_WEEKDAYS),
            ),
        ),
    )


def _should_send_followups_now(
    timestamp: datetime,
    *,
    start_hour: int = 9,
    start_minute: int = 0,
    end_hour: int = 16,
    end_minute: int = 30,
) -> bool:
    """Only send follow-ups during the configured business window."""
    return within_send_window(
        timestamp,
        timezone=_followup_send_window_timezone(),
        allowed_weekdays=_allowed_followup_weekdays(),
        start_hour=start_hour,
        start_minute=start_minute,
        end_hour=end_hour,
        end_minute=end_minute,
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Send due follow-up emails")
    parser.add_argument(
        "--state-path",
        default=DEFAULT_STATE_PATH,
        help="Outreach state file",
    )
    parser.add_argument(
        "--token-path",
        default=DEFAULT_GMAIL_STATE_PATH,
        help="Path to token.json",
    )
    parser.add_argument(
        "--creds-path",
        default=DEFAULT_CREDS_PATH,
        help="Path to credentials.json",
    )
    parser.add_argument(
        "--template-path",
        default=DEFAULT_TEMPLATE_PATH,
        help="Follow-up HTML template",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect due follow-ups without sending",
    )
    return parser.parse_args()


def _reply_headers(thread: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Return subject, in-reply-to, and references for the last message."""
    messages = thread.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return "", None, None

    payload = messages[-1].get("payload", {})
    headers = headers_to_dict(payload.get("headers"))  # type: ignore[arg-type]
    subject = headers.get("subject", "")
    message_id = headers.get("message-id")
    references = headers.get("references")
    if message_id and references and message_id not in references:
        references = f"{references} {message_id}".strip()
    elif message_id and not references:
        references = message_id
    return subject, message_id, references


def process_followups(
    *,
    state_path: str = DEFAULT_STATE_PATH,
    token_path: str = DEFAULT_GMAIL_STATE_PATH,
    creds_path: str = DEFAULT_CREDS_PATH,
    template_path: str = DEFAULT_TEMPLATE_PATH,
    dry_run: bool = False,
    state_store: OutreachStateStore | None = None,
) -> dict[str, int]:
    """Process due follow-ups and return the run summary fragment."""
    store = state_store or OutreachStateStore(state_path)
    pending = store.due_followups(max_followups=MAX_FOLLOWUPS)
    daily_limit = _followup_daily_limit()
    now = _now()
    if daily_limit is not None and len(pending) > daily_limit:
        pending = pending[:daily_limit]
    summary = {
        "followups_sent": 0,
        "replies_detected": 0,
        "bounces_detected": 0,
    }
    if not pending:
        return summary

    gmail_api, _ = load_authenticated_gmail(
        token_path=token_path,
        creds_path=creds_path,
    )
    sender_email = gmail_api.get_current_user()["emailAddress"]
    should_send_now = _should_send_followups_now(now)
    sendable_followups: list[tuple[dict[str, Any], str, Any]] = []
    deferred_followups = 0

    for contact in pending:
        thread_id = str(contact.get("thread_id", "")).strip()
        if not thread_id:
            continue

        thread = gmail_api.get_thread(thread_id)
        if not thread:
            continue

        detection = detect_thread_stop(
            thread,
            sender_email=sender_email,
            recipient_email=str(contact["email"]),
        )
        if detection.stop:
            if detection.status == "replied":
                summary["replies_detected"] += 1
            if detection.status == "bounced":
                summary["bounces_detected"] += 1
            if not dry_run:
                store.mark_reply_status(
                    str(contact["email"]),
                    status=detection.status,
                    reply_status=detection.reply_status,
                )
            continue

        company_record = store.companies.get(str(contact["company_key"]), {})
        hydrated_contact = dict(contact)
        hydrated_contact["company_display_name"] = company_record.get(
            "display_name",
            str(contact["company_key"]),
        )
        template = load_template(
            template_path,
            followup_count=int(contact.get("followup_count", 0)),
        )
        subject, in_reply_to, references = _reply_headers(thread)
        fallback_subject = str(contact.get("subject", "")).strip() or (
            f"Software Engineer - {hydrated_contact['company_display_name']}"
        )
        message = create_followup_message(
            hydrated_contact,
            template=template,
            subject=subject or fallback_subject,
            in_reply_to=in_reply_to,
            references=references,
        )
        if dry_run:
            summary["followups_sent"] += 1
            continue

        if not should_send_now:
            deferred_followups += 1
            continue
        sendable_followups.append((contact, thread_id, message))

    if dry_run:
        return summary

    if not should_send_now and deferred_followups:
        logger.info(
            "Deferring %s follow-up(s) until the next allowed send window",
            deferred_followups,
        )
        store.save()
        return summary

    send_times = paced_send_times(
        len(sendable_followups),
        now=now,
        timezone=_followup_send_window_timezone(),
        allowed_weekdays=_allowed_followup_weekdays(),
        minimum_spacing_minutes=_followup_min_spacing_minutes(),
    )
    if len(send_times) < len(sendable_followups):
        logger.info(
            "Deferring %s follow-up(s) to a later run to keep at least %s minutes "
            "between sends",
            len(sendable_followups) - len(send_times),
            _followup_min_spacing_minutes(),
        )
    for (contact, thread_id, message), send_time in zip(
        sendable_followups,
        send_times,
        strict=False,
    ):
        _sleep_until(send_time)
        sent = gmail_api.send_now(message, thread_id=thread_id)
        if not sent:
            continue
        store.mark_followup_sent(str(contact["email"]), max_followups=MAX_FOLLOWUPS)
        summary["followups_sent"] += 1

    store.save()
    return summary


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    summary = process_followups(
        state_path=args.state_path,
        token_path=args.token_path,
        creds_path=args.creds_path,
        template_path=args.template_path,
        dry_run=args.dry_run,
    )
    logger.info("followups_sent=%s", summary["followups_sent"])
    logger.info("replies_detected=%s", summary["replies_detected"])
    logger.info("bounces_detected=%s", summary["bounces_detected"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
