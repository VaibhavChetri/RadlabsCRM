"""
lead_service.py
---------------
Every write to a lead goes through here, so history rows (status changes,
calls) are always written. Functions add/flush but do NOT commit: the
caller owns the transaction (an import can then be all-or-nothing).
"""

from sqlalchemy.orm import Session

from models import Lead, Status, StatusChange, User

NEW_STATUS = "New"


def create_lead(db: Session, fields: dict, user: User) -> Lead:
    """Create a lead with status New, owned by its creator, and log none -> New."""
    new_status = db.query(Status).filter(Status.name == NEW_STATUS).one()
    lead = Lead(
        **fields,
        status_id=new_status.id,
        owner_id=user.id,
        created_by=user.id,
    )
    db.add(lead)
    db.flush()  # gets lead.id for the history row

    db.add(StatusChange(
        lead_id=lead.id,
        from_status_id=None,
        to_status_id=new_status.id,
        user_id=user.id,
        changed_at=lead.created_at,
    ))
    db.flush()
    return lead
