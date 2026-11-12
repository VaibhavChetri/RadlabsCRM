"""
lead_matcher.py
---------------
Is this person already in the CRM? Used by the import engine and by the
manual "Add lead" form.

Match order: email (lowercase), then phone (digits only, last 10 digits),
then LinkedIn URL (lowercase, no scheme, www, query or trailing slash).
"""

import re

from sqlalchemy.orm import Session

from models import Lead

MIN_PHONE_DIGITS = 7  # fewer digits than this is not a usable phone number


def email_key(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value if "@" in value else None


def phone_key(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= MIN_PHONE_DIGITS else None


def linkedin_key(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^www\.", "", value)
    value = re.split(r"[?#]", value)[0].rstrip("/")
    return value or None


# (lead field, how to turn its value into a match key), in match order.
KEYS = (
    ("email", email_key),
    ("phone", phone_key),
    ("linkedin_url", linkedin_key),
)


def has_contact(fields: dict) -> bool:
    """A lead we can reach: a usable email, phone or LinkedIn URL."""
    return any(to_key(fields.get(name)) for name, to_key in KEYS)


class LeadIndex:
    """Match keys of every lead, loaded once (fast enough for tens of thousands)."""

    def __init__(self):
        self._ids: dict[str, dict[str, int]] = {name: {} for name, _ in KEYS}

    @classmethod
    def load(cls, db: Session) -> "LeadIndex":
        index = cls()
        columns = [getattr(Lead, name) for name, _ in KEYS]
        for lead_id, *values in db.query(Lead.id, *columns):
            index.add(lead_id, dict(zip([name for name, _ in KEYS], values)))
        return index

    def add(self, lead_id: int, fields: dict) -> None:
        for name, to_key in KEYS:
            key = to_key(fields.get(name))
            if key:
                self._ids[name].setdefault(key, lead_id)

    def find(self, fields: dict) -> int | None:
        for name, to_key in KEYS:
            key = to_key(fields.get(name))
            if key and key in self._ids[name]:
                return self._ids[name][key]
        return None


# The only fields a merge may fill. Status, owner, notes, calls, follow-up,
# priority and source are sales work: a file never changes them.
MERGE_FIELDS = (
    "first_name", "last_name", "job_title", "email", "phone", "phone_2", "linkedin_url",
    "company", "website", "industry", "company_size", "city", "country",
)


def fields_to_fill(lead: Lead, candidate: dict) -> dict:
    """The candidate's values for fields that are empty on the existing lead."""
    return {
        name: candidate[name]
        for name in MERGE_FIELDS
        if candidate.get(name) and not getattr(lead, name)
    }
