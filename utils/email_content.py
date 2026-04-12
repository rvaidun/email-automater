"""Helpers for safe, deliverability-friendly email content."""

from __future__ import annotations

import re
from html import unescape

HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_BREAK_RE = re.compile(r"</p>|<br\s*/?>", re.IGNORECASE)
HTML_LINK_RE = re.compile(
    r'<a\s+[^>]*href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
INLINE_SUBJECT_RE = re.compile(
    r"<p>\s*Subject:\s*(?P<subject>.*?)\s*</p>\s*",
    re.IGNORECASE | re.DOTALL,
)
WRAPPER_TAG_RE = re.compile(r"</?(?:html|body)[^>]*>", re.IGNORECASE)


def _link_replacement(match: re.Match[str]) -> str:
    href = unescape(match.group("href")).strip()
    label_html = match.group("label")
    label_text = unescape(HTML_TAG_RE.sub("", label_html)).strip()
    if not label_text:
        return href
    normalized_href = re.sub(r"^https?://", "", href, flags=re.IGNORECASE).rstrip("/")
    normalized_label = label_text.rstrip("/")
    if label_text == href or normalized_label.lower() == normalized_href.lower():
        return label_text
    return f"{label_text} ({href})"


def split_inline_subject(message_body: str) -> tuple[str | None, str]:
    """Return an optional inline subject plus HTML body without that paragraph."""
    match = INLINE_SUBJECT_RE.search(message_body)
    if not match:
        return None, message_body
    prefix = message_body[: match.start()]
    prefix_without_wrappers = WRAPPER_TAG_RE.sub("", prefix).strip()
    if prefix_without_wrappers:
        return None, message_body
    subject_html = match.group("subject")
    subject = HTML_TAG_RE.sub("", subject_html)
    cleaned_subject = unescape(subject).strip()
    cleaned_body = f"{prefix}{message_body[match.end() :]}".lstrip()
    return cleaned_subject or None, cleaned_body


def html_to_plain_text(message_body: str) -> str:
    """Convert simple HTML email content into plain text for deliverability."""
    normalized = HTML_LINK_RE.sub(_link_replacement, message_body)
    normalized = HTML_BREAK_RE.sub("\n\n", normalized)
    normalized = HTML_TAG_RE.sub("", normalized)
    normalized = unescape(normalized)
    lines = [line.strip() for line in normalized.splitlines()]
    non_empty = [line for line in lines if line]
    return "\n\n".join(non_empty)
