"""
lead_query.py
-------------
Read-only queries over leads. Nothing here writes.

search_leads the All-leads table: search, filters, sort, page.
all_leads    every lead that matches (for the Excel export).
notes_by_lead  the notes thread of every matching lead, newest first.
today_list   the caller's home-screen call list, in three sections.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from lead_service import NEW_STATUS
from models import Import, Lead, LeadNote, Status, User

UNASSIGNED = "unassigned"

# Hot first. Explicit, so it does not depend on the ENUM's column order.
PRIORITY_RANK = case({"hot": 0, "warm": 1, "cold": 2}, value=Lead.priority)


# Table sort keys -> column. Blank values always sort last.
SORT_COLUMNS = {
    "added": Lead.created_at,
    "last_called": Lead.last_called_at,
    "follow_up": Lead.next_follow_up,
    "priority": PRIORITY_RANK,
    "company": func.lower(Lead.company),
}
# Direction used when the caller does not choose one: newest / most recent first.
DEFAULT_ORDER = {"added": "desc", "last_called": "desc"}


@dataclass
class LeadSort:
    key: str = "added"
    order: str | None = None  # "asc" | "desc"; None = the key's default

    def order_by(self) -> list:
        column = SORT_COLUMNS[self.key]
        direction = self.order or DEFAULT_ORDER.get(self.key, "asc")
        if self.key == "added":
            return [getattr(column, direction)(), getattr(Lead.id, direction)()]
        # Ties (and blanks) fall back to newest added first, so pages are stable.
        return [column.is_(None), getattr(column, direction)(),
                Lead.created_at.desc(), Lead.id.desc()]


@dataclass
class LeadFilters:
    """What the All-leads table (and its export) is narrowed by."""
    q: str | None = None
    statuses: list[str] = field(default_factory=list)    # any of these
    sources: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)      # user uuids and/or UNASSIGNED
    added_from: date | None = None  # the user's local dates, both ends included
    added_to: date | None = None
    tz_offset: int = 0              # user's local time minus UTC, in minutes (IST = 330)
    import_uuid: str | None = None  # only the leads this import added

    def local_day_start_utc(self, day: date) -> datetime:
        """Midnight of `day` in the user's time zone, as naive UTC (what we store)."""
        return datetime.combine(day, time.min) - timedelta(minutes=self.tz_offset)


def _search_condition(q: str):
    """Every word must match the name, company, email or phone."""
    full_name = func.concat_ws(" ", Lead.first_name, Lead.last_name)
    conditions = []
    for word in q.split():
        # autoescape: a typed "%" or "_" is matched as itself, not as a wildcard.
        matches = [column.icontains(word, autoescape=True) for column in
                   (full_name, Lead.company, Lead.email, Lead.phone, Lead.phone_2)]
        digits = re.sub(r"\D", "", word)
        if digits:
            # "98765 43210", "+91-98765-43210" and "9876543210" all match.
            for phone in (Lead.phone, Lead.phone_2):
                matches.append(func.regexp_replace(phone, "[^0-9]", "").contains(digits))
        conditions.append(or_(*matches))
    return and_(*conditions)


def _owner_condition(owners: list[str]):
    owner_uuids = [o for o in owners if o != UNASSIGNED]
    conditions = []
    if UNASSIGNED in owners:
        conditions.append(Lead.owner_id.is_(None))
    if owner_uuids:
        ids = select(User.id).where(User.uuid.in_(owner_uuids))
        conditions.append(Lead.owner_id.in_(ids))
    return or_(*conditions)


def _filtered(db: Session, filters: LeadFilters):
    query = db.query(Lead)
    if filters.q and filters.q.strip():
        query = query.filter(_search_condition(filters.q))
    if filters.statuses:
        query = query.join(Lead.status).filter(Status.name.in_(filters.statuses))
    if filters.sources:
        query = query.filter(Lead.source.in_(filters.sources))
    if filters.import_uuid:
        query = query.filter(Lead.import_id.in_(
            select(Import.id).where(Import.uuid == filters.import_uuid)))
    if filters.priorities:
        query = query.filter(Lead.priority.in_(filters.priorities))
    if filters.owners:
        query = query.filter(_owner_condition(filters.owners))
    if filters.added_from:
        query = query.filter(Lead.created_at >= filters.local_day_start_utc(filters.added_from))
    if filters.added_to:
        day_after = filters.added_to + timedelta(days=1)
        query = query.filter(Lead.created_at < filters.local_day_start_utc(day_after))
    return query


def _with_display_fields(query, sort: LeadSort):
    return query.options(
        joinedload(Lead.status), joinedload(Lead.owner), joinedload(Lead.creator),
    ).order_by(*sort.order_by())


def search_leads(
    db: Session, filters: LeadFilters, sort: LeadSort, page: int = 1, page_size: int = 50,
) -> tuple[list[Lead], int]:
    """One page of the All-leads table (pages start at 1), plus the total count."""
    query = _filtered(db, filters)
    total = query.count()
    rows = (
        _with_display_fields(query, sort)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def all_leads(db: Session, filters: LeadFilters, sort: LeadSort) -> list[Lead]:
    return _with_display_fields(_filtered(db, filters), sort).all()


def notes_by_lead(db: Session, filters: LeadFilters) -> dict[int, list[LeadNote]]:
    """lead id -> its notes, newest first, for every lead that matches."""
    matching_ids = _filtered(db, filters).with_entities(Lead.id).scalar_subquery()
    notes = (
        db.query(LeadNote)
        .options(joinedload(LeadNote.author))
        .filter(LeadNote.lead_id.in_(matching_ids))
        .order_by(LeadNote.created_at.desc(), LeadNote.id.desc())
        .all()
    )
    grouped: dict[int, list[LeadNote]] = {}
    for note in notes:
        grouped.setdefault(note.lead_id, []).append(note)
    return grouped


def today_list(db: Session, user: User, today: date) -> dict[str, list[Lead]]:
    """The caller's call list for `today` (the caller's local date)."""
    mine = (
        db.query(Lead)
        .join(Lead.status)
        .options(contains_eager(Lead.status), joinedload(Lead.owner), joinedload(Lead.creator))
        .filter(Lead.owner_id == user.id, Status.is_exit.is_(False))
    )
    return {
        # Most-missed first.
        "overdue": mine.filter(Lead.next_follow_up < today)
        .order_by(Lead.next_follow_up, PRIORITY_RANK, Lead.id).all(),
        "due_today": mine.filter(Lead.next_follow_up == today)
        .order_by(PRIORITY_RANK, Lead.id).all(),
        # A New lead with a follow-up due is already listed above.
        # Oldest first on the same priority, so no lead waits for ever.
        "new": mine.filter(
            Status.name == NEW_STATUS,
            or_(Lead.next_follow_up.is_(None), Lead.next_follow_up > today),
        ).order_by(PRIORITY_RANK, Lead.created_at, Lead.id).all(),
    }
