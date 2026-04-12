# ruff: noqa: PLR0913
"""JSON state management for the outreach pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from utils.company_normalize import clean_company_display_name, company_key

DEFAULT_STATE_PATH = Path("state/outreach_state.json")
CONTACT_WINDOW_DAYS = 60
FOLLOWUP_WAIT_DAYS = 3
MAX_FOLLOWUPS = 2
MAX_COMPANY_CONTACTS_PER_WINDOW = 2


def default_state() -> dict[str, Any]:
    """Return the default state payload."""
    return {"companies": {}, "contacts": {}, "runs": []}


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp if present."""
    if not value:
        return None
    return datetime.fromisoformat(value)


def _isoformat(value: datetime) -> str:
    return value.isoformat()


class OutreachStateStore:
    """Persist outreach history in a JSON file."""

    def __init__(
        self,
        path: str | Path = DEFAULT_STATE_PATH,
        *,
        timezone: str = "America/New_York",
    ) -> None:
        """Initialize the state store."""
        self.path = Path(path)
        self.timezone = ZoneInfo(timezone)
        self.data = default_state()
        self.load()

    @property
    def companies(self) -> dict[str, dict[str, Any]]:
        """Return company records."""
        return self.data["companies"]

    @property
    def contacts(self) -> dict[str, dict[str, Any]]:
        """Return contact records keyed by email."""
        return self.data["contacts"]

    @property
    def runs(self) -> list[dict[str, Any]]:
        """Return recorded run summaries."""
        return self.data["runs"]

    def load(self) -> dict[str, Any]:
        """Load state from disk, creating it if missing."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.data = default_state()
            self.save()
            return self.data

        self.data = json.loads(self.path.read_text())
        for key, value in default_state().items():
            self.data.setdefault(key, value)
        return self.data

    def save(self) -> None:
        """Persist state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")

    def now(self) -> datetime:
        """Return the current time in the configured timezone."""
        return datetime.now(self.timezone)

    def _local_date(self, value: datetime) -> object:
        """Normalize a timestamp to the store timezone before comparing dates."""
        return value.astimezone(self.timezone).date()

    def _contact_key(self, email: str) -> str:
        return email.strip().lower()

    def mark_company_seen(
        self,
        display_name: str,
        *,
        source: str,
        seen_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create or update a company record."""
        timestamp = seen_at or self.now()
        key = company_key(display_name)
        cleaned_display = clean_company_display_name(display_name)
        record = self.companies.get(
            key,
            {
                "canonical_name": cleaned_display,
                "display_name": cleaned_display,
                "status": "seen",
                "last_seen_at": _isoformat(timestamp),
                "last_contacted_at": None,
                "cooldown_until": None,
                "contacts_sent_60d": 0,
                "source": source,
            },
        )
        record["canonical_name"] = cleaned_display
        record["display_name"] = cleaned_display
        record["last_seen_at"] = _isoformat(timestamp)
        record["source"] = source
        record["contacts_sent_60d"] = self.contacts_sent_within_days(
            key,
            days=CONTACT_WINDOW_DAYS,
            now=timestamp,
        )
        self.companies[key] = record
        return record

    def has_contact(self, email: str) -> bool:
        """Return True when the contact is already tracked."""
        return self._contact_key(email) in self.contacts

    def contacts_sent_within_days(
        self,
        company_name_or_key: str,
        *,
        days: int,
        now: datetime | None = None,
    ) -> int:
        """Count contacted records for a company inside a rolling window."""
        timestamp = now or self.now()
        key = company_key(company_name_or_key)
        cutoff = timestamp - timedelta(days=days)
        count = 0
        for record in self.contacts.values():
            if record.get("company_key") != key:
                continue
            sent_at = parse_datetime(record.get("sent_at"))
            if sent_at is None or sent_at < cutoff:
                continue
            if record.get("status") in {"candidate", "skipped"}:
                continue
            count += 1
        return count

    def was_company_contacted_today(
        self,
        company_name_or_key: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return True when the company already received outreach today."""
        timestamp = now or self.now()
        key = company_key(company_name_or_key)
        for record in self.contacts.values():
            if record.get("company_key") != key:
                continue
            sent_at = parse_datetime(record.get("sent_at"))
            if sent_at is not None and sent_at.date() == timestamp.date():
                return True
        return False

    def is_company_on_cooldown(
        self,
        company_name_or_key: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return True when the company cooldown window is still active."""
        key = company_key(company_name_or_key)
        record = self.companies.get(key)
        if not record:
            return False
        cooldown_until = parse_datetime(record.get("cooldown_until"))
        if cooldown_until is None:
            return False
        return cooldown_until > (now or self.now())

    def can_contact_company(
        self,
        company_name_or_key: str,
        *,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        """Return whether a company can be contacted today."""
        timestamp = now or self.now()
        key = company_key(company_name_or_key)
        if self.is_company_on_cooldown(key, now=timestamp):
            return False, "cooldown"
        if self.was_company_contacted_today(key, now=timestamp):
            return False, "daily_limit"
        if (
            self.contacts_sent_within_days(
                key,
                days=CONTACT_WINDOW_DAYS,
                now=timestamp,
            )
            >= MAX_COMPANY_CONTACTS_PER_WINDOW
        ):
            return False, "sixty_day_limit"
        return True, ""

    def upsert_contact(
        self,
        *,
        email: str,
        company_name: str,
        name: str,
        title: str,
        source: str,
        status: str = "candidate",
        thread_id: str | None = None,
        sent_at: datetime | None = None,
        followup_count: int = 0,
        next_followup_at: datetime | None = None,
        reply_status: str = "none",
        **extra: object,
    ) -> dict[str, Any]:
        """Create or update a contact record."""
        key = self._contact_key(email)
        company_name_key = company_key(company_name)
        timestamp = sent_at or self.now()
        record = self.contacts.get(
            key,
            {
                "company_key": company_name_key,
                "name": name,
                "title": title,
                "email": email,
                "status": status,
                "thread_id": thread_id,
                "sent_at": _isoformat(timestamp) if sent_at else None,
                "followup_count": followup_count,
                "next_followup_at": _isoformat(next_followup_at)
                if next_followup_at
                else None,
                "reply_status": reply_status,
                "source": source,
            },
        )
        record["company_key"] = company_name_key
        record["name"] = name
        record["title"] = title
        record["email"] = email
        record["status"] = status
        record["thread_id"] = thread_id or record.get("thread_id")
        record["reply_status"] = reply_status
        record["source"] = source
        if sent_at:
            record["sent_at"] = _isoformat(sent_at)
        if next_followup_at is not None:
            record["next_followup_at"] = _isoformat(next_followup_at)
        record["followup_count"] = followup_count
        record.update(extra)
        self.contacts[key] = record
        return record

    def mark_contact_queued(
        self,
        *,
        email: str,
        company_name: str,
        name: str,
        title: str,
        thread_id: str,
        source: str,
        scheduled_for: datetime,
        actioned_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Record a scheduled outreach email."""
        record = self.upsert_contact(
            email=email,
            company_name=company_name,
            name=name,
            title=title,
            source=source,
            status="queued",
            thread_id=thread_id,
            sent_at=scheduled_for,
            followup_count=0,
            next_followup_at=scheduled_for + timedelta(days=FOLLOWUP_WAIT_DAYS),
            reply_status="none",
            actioned_at=_isoformat(actioned_at or self.now()),
        )
        self._mark_company_contacted(company_name, scheduled_for)
        return record

    def mark_contact_sent(
        self,
        *,
        email: str,
        company_name: str,
        name: str,
        title: str,
        thread_id: str,
        source: str,
        sent_at: datetime | None = None,
        actioned_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Record an immediate send."""
        timestamp = sent_at or self.now()
        record = self.upsert_contact(
            email=email,
            company_name=company_name,
            name=name,
            title=title,
            source=source,
            status="sent",
            thread_id=thread_id,
            sent_at=timestamp,
            followup_count=0,
            next_followup_at=timestamp + timedelta(days=FOLLOWUP_WAIT_DAYS),
            reply_status="none",
            actioned_at=_isoformat(actioned_at or timestamp),
        )
        self._mark_company_contacted(company_name, timestamp)
        return record

    def _mark_company_contacted(self, company_name: str, sent_at: datetime) -> None:
        record = self.mark_company_seen(
            company_name,
            source="newgrad-jobs",
            seen_at=sent_at,
        )
        key = company_key(company_name)
        record["status"] = "cooldown"
        record["last_contacted_at"] = _isoformat(sent_at)
        record["cooldown_until"] = _isoformat(
            sent_at + timedelta(days=CONTACT_WINDOW_DAYS)
        )
        record["contacts_sent_60d"] = self.contacts_sent_within_days(
            key,
            days=CONTACT_WINDOW_DAYS,
            now=sent_at + timedelta(seconds=1),
        )
        self.companies[key] = record

    def due_followups(
        self,
        *,
        now: datetime | None = None,
        max_followups: int = MAX_FOLLOWUPS,
    ) -> list[dict[str, Any]]:
        """Return contacts with follow-ups due."""
        timestamp = now or self.now()
        due: list[dict[str, Any]] = []
        for record in self.contacts.values():
            next_followup_at = parse_datetime(record.get("next_followup_at"))
            if next_followup_at is None:
                continue
            if self._local_date(next_followup_at) > self._local_date(timestamp):
                continue
            if record.get("followup_count", 0) >= max_followups:
                continue
            if record.get("status") not in {"queued", "sent"}:
                continue
            due.append(record)
        due.sort(key=lambda item: item.get("next_followup_at") or "")
        return due

    def mark_followup_sent(
        self,
        email: str,
        *,
        sent_at: datetime | None = None,
        max_followups: int = MAX_FOLLOWUPS,
    ) -> dict[str, Any]:
        """Increment follow-up state for a contact."""
        timestamp = sent_at or self.now()
        key = self._contact_key(email)
        record = self.contacts[key]
        followup_count = int(record.get("followup_count", 0)) + 1
        record["followup_count"] = followup_count
        record["status"] = "closed" if followup_count >= max_followups else "sent"
        record["sent_at"] = _isoformat(timestamp)
        record["next_followup_at"] = (
            None
            if followup_count >= max_followups
            else _isoformat(timestamp + timedelta(days=FOLLOWUP_WAIT_DAYS))
        )
        self.contacts[key] = record
        return record

    def mark_reply_status(
        self,
        email: str,
        *,
        status: str,
        reply_status: str,
    ) -> dict[str, Any]:
        """Update a contact after a reply, bounce, or opt-out."""
        key = self._contact_key(email)
        record = self.contacts[key]
        record["status"] = status
        record["reply_status"] = reply_status
        record["next_followup_at"] = None
        self.contacts[key] = record
        return record

    def new_outreach_actions_on_day(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        """Count new outreach actions already taken on the provided day."""
        timestamp = now or self.now()
        count = 0
        active_statuses = {
            "queued",
            "sent",
            "replied",
            "bounced",
            "opt_out",
            "closed",
        }
        for record in self.contacts.values():
            if record.get("status") not in active_statuses:
                continue
            actioned_at = parse_datetime(record.get("actioned_at"))
            sent_at = parse_datetime(record.get("sent_at"))
            reference_time = actioned_at or sent_at
            if reference_time and reference_time.date() == timestamp.date():
                count += 1
        return count

    def append_run(self, summary: dict[str, Any]) -> None:
        """Persist a run summary."""
        self.runs.append(summary)
