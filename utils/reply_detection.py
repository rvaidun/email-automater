"""Reply and stop-condition detection for Gmail threads."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parseaddr

BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
BOUNCE_KEYWORDS = [
    "delivery has failed",
    "delivery status notification",
    "undeliverable",
    "address not found",
    "message blocked",
]
AUTO_REPLY_KEYWORDS = [
    "automatic reply",
    "auto reply",
    "out of office",
    "vacation responder",
]
OPT_OUT_KEYWORDS = [
    "do not contact",
    "don't contact",
    "do not email",
    "remove me",
    "unsubscribe",
    "stop emailing",
    "not interested",
]


@dataclass(slots=True)
class ReplyDetectionResult:
    """Structured stop-condition result for a thread."""

    stop: bool
    status: str
    reply_status: str
    reason: str


def headers_to_dict(headers: list[Mapping[str, str]] | None) -> dict[str, str]:
    """Convert Gmail headers into a case-insensitive-ish mapping."""
    result: dict[str, str] = {}
    for header in headers or []:
        name = header.get("name")
        value = header.get("value")
        if name and value:
            result[name.lower()] = value
    return result


def extract_email_address(value: str | None) -> str:
    """Return the email portion of a header value."""
    return parseaddr(value or "")[1].strip().lower()


def _decode_part_body(body: Mapping[str, str] | None) -> str:
    if not body:
        return ""
    data = body.get("data", "")
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    return decoded.decode("utf-8", errors="ignore")


def extract_body_text(payload: Mapping[str, object] | None) -> str:
    """Extract body text from a Gmail payload tree."""
    if not payload:
        return ""

    body_text = _decode_part_body(payload.get("body"))  # type: ignore[arg-type]
    if body_text:
        return body_text

    parts = payload.get("parts", [])
    if not isinstance(parts, list):
        return ""

    return "\n".join(
        part_text
        for part in parts
        if isinstance(part, Mapping)
        for part_text in [extract_body_text(part)]
        if part_text
    )


def detect_thread_stop(
    thread: Mapping[str, object],
    *,
    sender_email: str,
    recipient_email: str,
) -> ReplyDetectionResult:
    """Inspect a Gmail thread for replies, bounces, or opt-outs."""
    normalized_sender = sender_email.strip().lower()
    normalized_recipient = recipient_email.strip().lower()

    messages = thread.get("messages", [])
    if not isinstance(messages, list):
        return ReplyDetectionResult(
            stop=False,
            status="sent",
            reply_status="none",
            reason="",
        )

    for message in messages:
        if not isinstance(message, Mapping):
            continue
        payload = message.get("payload")
        if not isinstance(payload, Mapping):
            continue
        headers = headers_to_dict(payload.get("headers"))  # type: ignore[arg-type]
        from_header = headers.get("from", "")
        from_email = extract_email_address(from_header)
        subject = headers.get("subject", "").lower()
        body_text = extract_body_text(payload).lower()
        snippet = str(message.get("snippet", "")).lower()
        combined = " ".join(part for part in [subject, snippet, body_text] if part)

        if from_email == normalized_sender:
            continue

        if any(keyword in from_email for keyword in BOUNCE_SENDERS) or any(
            keyword in combined for keyword in BOUNCE_KEYWORDS
        ):
            return ReplyDetectionResult(
                stop=True,
                status="bounced",
                reply_status="bounce",
                reason="bounce",
            )

        if headers.get("auto-submitted", "").lower() == "auto-generated" or any(
            keyword in combined for keyword in AUTO_REPLY_KEYWORDS
        ):
            return ReplyDetectionResult(
                stop=True,
                status="closed",
                reply_status="auto_reply",
                reason="auto_reply",
            )

        if any(keyword in combined for keyword in OPT_OUT_KEYWORDS):
            return ReplyDetectionResult(
                stop=True,
                status="opt_out",
                reply_status="opt_out",
                reason="opt_out",
            )

        if from_email and (
            from_email == normalized_recipient or from_email != normalized_sender
        ):
            return ReplyDetectionResult(
                stop=True,
                status="replied",
                reply_status="replied",
                reason="reply",
            )

    return ReplyDetectionResult(
        stop=False,
        status="sent",
        reply_status="none",
        reason="",
    )
