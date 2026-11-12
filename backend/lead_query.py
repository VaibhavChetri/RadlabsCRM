"""
lead_query.py
-------------
Read-only queries over leads. Nothing here writes.

today_list   the caller's home-screen call list, in three sections.
"""

from datetime import date

from sqlalchemy import case, or_
from sqlalchemy.orm import Session, contains_eager, joinedload

from lead_service import NEW_STATUS
from models import Lead, Status, User

# Hot first. Explicit, so it does not depend on the ENUM's column order.
PRIORITY_RANK = case({"hot": 0, "warm": 1, "cold": 2}, value=Lead.priority)


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
