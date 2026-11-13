"""
stats_engine.py
---------------
Numbers for the analytics strip and the Team stats page. Read-only.

A Period is a range of the user's LOCAL dates (both ends included) plus the
user's offset from UTC, because times are stored as naive UTC.

summary     cards + charts, for one user ("Me") or the whole team
team_table  one row per person, for the Team stats page

"Meetings booked" and "Won" come from status_changes inside the period, so
moving a lead out of Won later does not change a past period.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, literal_column
from sqlalchemy.orm import Session

from models import SOURCES, Call, Lead, Status, StatusChange, User

MEETING_BOOKED = "Meeting booked"
WON = "Won"
MAX_DAYS = 366  # keeps the per-day charts a sane size


class PeriodError(ValueError):
    """A period that cannot be shown (backwards, or too long)."""


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    tz_offset: int = 0  # local time minus UTC, in minutes (IST = 330)

    def __post_init__(self):
        if self.start > self.end:
            raise PeriodError("The start date must be on or before the end date")
        if (self.end - self.start).days + 1 > MAX_DAYS:
            raise PeriodError(f"Pick a period of {MAX_DAYS} days or less")

    @property
    def start_utc(self) -> datetime:
        return self._local_midnight_utc(self.start)

    @property
    def end_utc(self) -> datetime:
        """Exclusive: midnight after the last day."""
        return self._local_midnight_utc(self.end + timedelta(days=1))

    def days(self) -> list[date]:
        return [self.start + timedelta(days=n) for n in range((self.end - self.start).days + 1)]

    def contains(self, column):
        """SQL condition: the UTC `column` falls on one of the period's local days."""
        return (column >= self.start_utc) & (column < self.end_utc)

    def local_date(self, column):
        """SQL expression: the user's local date of a UTC `column`."""
        return func.date(func.timestampadd(literal_column("MINUTE"), self.tz_offset, column))

    def _local_midnight_utc(self, day: date) -> datetime:
        return datetime.combine(day, time.min) - timedelta(minutes=self.tz_offset)


def summary(db: Session, period: Period, user: User | None = None) -> dict:
    """Cards and charts. `user` = "Me" scope; None = the whole team.
    Me = calls I made, leads I own, and status changes I made."""
    calls = db.query(Call).filter(period.contains(Call.called_at))
    leads = db.query(Lead)
    if user is not None:
        calls = calls.filter(Call.user_id == user.id)
        leads = leads.filter(Lead.owner_id == user.id)
    added = leads.filter(period.contains(Lead.created_at))
    added_count = added.count()
    won = _moved_into(db, WON, period, user)
    return {
        "cards": {
            "total_leads": leads.count(),
            "calls": calls.count(),
            "leads_added": added_count,
            "follow_ups_due": _follow_ups_due(leads, period),
            "meetings_booked": _moved_into(db, MEETING_BOOKED, period, user),
            "won": won,
            # Won in the period / added in the period. No leads added -> no rate.
            "conversion_pct": round(100 * won / added_count, 1) if added_count else None,
        },
        "funnel": _funnel(db, leads),
        "calls_per_day": _per_day(calls, Call.called_at, period),
        "added_per_day": _per_day(added, Lead.created_at, period),
        "by_source": _by_source(added),
    }


def _per_day(query, column, period: Period) -> list[dict]:
    """Rows of `query` counted per local day of `column`. Days with none are 0."""
    day = period.local_date(column)
    counts = dict(query.with_entities(day, func.count()).group_by(day).all())
    return [{"date": d.isoformat(), "count": counts.get(d, 0)} for d in period.days()]


DISTINCT_LEADS = func.count(func.distinct(StatusChange.lead_id))  # a lead counts once


def _moved_into(db: Session, status_name: str, period: Period, user: User | None) -> int:
    """Leads moved into `status_name` during the period (by `user`, if given).
    Counted by the change, not the lead's current status."""
    changes = _changes_into(db, status_name, period)
    if user is not None:
        changes = changes.filter(StatusChange.user_id == user.id)
    return changes.with_entities(DISTINCT_LEADS).scalar()


def _moved_into_by_user(db: Session, status_name: str, period: Period) -> dict[int, int]:
    """user id -> leads that user moved into `status_name` during the period."""
    return dict(
        _changes_into(db, status_name, period)
        .with_entities(StatusChange.user_id, DISTINCT_LEADS)
        .group_by(StatusChange.user_id)
        .all()
    )


def _changes_into(db: Session, status_name: str, period: Period):
    return (
        db.query(StatusChange)
        .join(Status, Status.id == StatusChange.to_status_id)
        .filter(Status.name == status_name, period.contains(StatusChange.changed_at))
    )


def _funnel(db: Session, leads) -> list[dict]:
    """Current status of `leads`, across all stages in pipeline order (empty stages = 0)."""
    counts = dict(leads.with_entities(Lead.status_id, func.count()).group_by(Lead.status_id).all())
    return [
        {"status": s.name, "is_exit": s.is_exit, "count": counts.get(s.id, 0)}
        for s in db.query(Status).order_by(Status.sort_order)
    ]


def _follow_ups_due(leads, period: Period) -> int:
    """Open leads (not in an exit stage) with a follow-up date inside the period.
    next_follow_up is already a local date, so no time-zone shift."""
    return (
        leads.join(Lead.status)
        .filter(Status.is_exit.is_(False),
                Lead.next_follow_up >= period.start, Lead.next_follow_up <= period.end)
        .count()
    )


def _by_source(leads) -> list[dict]:
    """`leads` counted per source, every source listed (empty = 0)."""
    counts = dict(leads.with_entities(Lead.source, func.count()).group_by(Lead.source).all())
    return [{"source": source, "count": counts.get(source, 0)} for source in SOURCES]


def team_table(db: Session, period: Period) -> dict:
    """One row per person: calls, meetings booked and won in the period
    (by who did it), and the leads they own now by current status.
    Active users always; deactivated users only if they did something in the
    period (a call or a status change), so past periods stay correct."""
    statuses = db.query(Status).order_by(Status.sort_order).all()
    status_names = {s.id: s.name for s in statuses}
    calls = dict(
        db.query(Call.user_id, func.count())
        .filter(period.contains(Call.called_at)).group_by(Call.user_id).all()
    )
    meetings = _moved_into_by_user(db, MEETING_BOOKED, period)
    won = _moved_into_by_user(db, WON, period)
    owned: dict[int, dict[str, int]] = {}
    for owner_id, status_id, count in (
        db.query(Lead.owner_id, Lead.status_id, func.count())
        .filter(Lead.owner_id.is_not(None)).group_by(Lead.owner_id, Lead.status_id)
    ):
        owned.setdefault(owner_id, {})[status_names[status_id]] = count

    changed = {
        user_id for (user_id,) in
        db.query(StatusChange.user_id).filter(period.contains(StatusChange.changed_at)).distinct()
    }
    active_in_period = set(calls) | changed

    rows = []
    for person in db.query(User).order_by(User.name, User.id):
        if not person.is_active and person.id not in active_in_period:
            continue
        by_status = {s.name: owned.get(person.id, {}).get(s.name, 0) for s in statuses}
        rows.append({
            "uuid": person.uuid,
            "name": person.name,
            "is_active": person.is_active,
            "calls": calls.get(person.id, 0),
            "meetings_booked": meetings.get(person.id, 0),
            "won": won.get(person.id, 0),
            "leads": sum(by_status.values()),
            "by_status": by_status,
        })
    return {"statuses": [s.name for s in statuses], "rows": rows}
