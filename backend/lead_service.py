"""
lead_service.py
---------------
Every write to a lead goes through here, so history rows (status changes,
calls) are always written. Functions add/flush but do NOT commit: the
caller owns the transaction (an import can then be all-or-nothing).
"""

from sqlalchemy.orm import Session

from models import Call, Lead, LeadNote, Status, StatusChange, User, utc_now

NEW_STATUS = "New"


class LeadError(ValueError):
    """A change that breaks a lead rule (unknown status, inactive owner, ...)."""


CREATOR = object()  # create_lead's default owner: whoever adds the lead


def create_lead(db: Session, fields: dict, user: User, owner: User | None = CREATOR) -> Lead:
    """Create a lead with status New and log none -> New.
    Owned by its creator unless `owner` is given (None = Unassigned)."""
    new_status = db.query(Status).filter(Status.name == NEW_STATUS).one()
    if owner is CREATOR:
        owner = user
    lead = Lead(
        **fields,
        status_id=new_status.id,
        owner_id=owner.id if owner else None,
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


def log_call(db: Session, lead: Lead, user: User) -> Lead:
    """+1 Call: count it, set Last called, and write one calls row."""
    now = utc_now()
    lead.call_attempts = (lead.call_attempts or 0) + 1
    lead.last_called_at = now
    db.add(Call(lead_id=lead.id, user_id=user.id, called_at=now))
    db.flush()
    return lead


# Priority follows the stage a lead moves to. New and Attempted leave it alone
# (nobody has talked to the lead yet), and so does moving to the same stage.
PRIORITY_FOR_STATUS = {
    # Interest shown: call these first.
    "Interested": "hot",
    "Meeting booked": "hot",
    "Proposal sent": "hot",
    # Closed: off the call list, nothing left to chase.
    "Won": "cold",
    "Lost": "cold",
    "Not interested": "cold",
    "Do not call": "cold",
}
# Raised to at least this, never lowered: a real conversation lifts a Cold
# lead, but must not undo a Hot set by hand.
MIN_PRIORITY_FOR_STATUS = {"Connected": "warm"}
_RANK = {"cold": 0, "warm": 1, "hot": 2}


def priority_after(status_name: str, current: str) -> str:
    """The priority a lead gets when it moves to `status_name`."""
    if status_name in PRIORITY_FOR_STATUS:
        return PRIORITY_FOR_STATUS[status_name]
    floor = MIN_PRIORITY_FOR_STATUS.get(status_name)
    if floor and _RANK[current] < _RANK[floor]:
        return floor
    return current


def change_status(db: Session, lead: Lead, status_name: str, user: User) -> Lead:
    """Move the lead to another stage and log from -> to. Same stage = no-op.
    The priority follows the new stage (see PRIORITY_FOR_STATUS)."""
    new_status = db.query(Status).filter(Status.name == status_name).first()
    if new_status is None:
        raise LeadError(f"Unknown status: {status_name}")
    if new_status.id == lead.status_id:
        return lead

    db.add(StatusChange(
        lead_id=lead.id,
        from_status_id=lead.status_id,
        to_status_id=new_status.id,
        user_id=user.id,
        changed_at=utc_now(),
    ))
    lead.status_id = new_status.id
    lead.status = new_status
    lead.priority = priority_after(new_status.name, lead.priority)
    db.flush()
    return lead


# Fields a PATCH copies straight onto the lead.
PLAIN_FIELDS = (
    "first_name", "last_name", "job_title", "email", "phone", "phone_2",
    "linkedin_url", "company", "website", "industry", "company_size", "city",
    "country", "source", "priority", "next_follow_up",
)
NOT_NULL_FIELDS = ("source", "priority")


def update_lead(db: Session, lead: Lead, changes: dict, user: User) -> Lead:
    """Apply a PATCH. Status goes through change_status so history is written
    (and the priority follows the stage, unless a priority is sent too)."""
    for field in PLAIN_FIELDS:
        if field not in changes:
            continue
        if changes[field] is None and field in NOT_NULL_FIELDS:
            raise LeadError(f"{field} cannot be empty")
        setattr(lead, field, changes[field])
    _check_name_and_contact(lead)

    if "status" in changes:
        change_status(db, lead, changes["status"], user)
        if changes.get("priority"):
            lead.priority = changes["priority"]  # chosen by hand: beats the automatic one
    if "owner_uuid" in changes:
        change_owner(db, lead, changes["owner_uuid"])
    db.flush()
    return lead


def change_owner(db: Session, lead: Lead, owner_uuid: str | None) -> Lead:
    """Hand the lead to an active user, or None for Unassigned."""
    if owner_uuid is None:
        lead.owner_id = None
        lead.owner = None
    else:
        owner = db.query(User).filter(User.uuid == owner_uuid, User.is_active.is_(True)).first()
        if owner is None:
            raise LeadError("Owner must be an active team member")
        lead.owner_id = owner.id
        lead.owner = owner
    db.flush()
    return lead


def reassign_leads(db: Session, from_user: User, to_uuid: str | None) -> int:
    """Hand every lead `from_user` owns to another active user (None = Unassigned).
    Lead by lead through change_owner, so the same rules apply. Returns the count."""
    if to_uuid == from_user.uuid:
        raise LeadError("Choose a different person")
    leads = db.query(Lead).filter(Lead.owner_id == from_user.id).all()
    for lead in leads:
        change_owner(db, lead, to_uuid)
    if not leads and to_uuid is not None:
        # Still refuse an invalid target, even when there is nothing to move.
        if not db.query(User).filter(User.uuid == to_uuid, User.is_active.is_(True)).first():
            raise LeadError("Owner must be an active team member")
    return len(leads)


def _check_name_and_contact(lead: Lead) -> None:
    if not (lead.first_name or lead.last_name):
        raise LeadError("A lead needs a first or last name")
    if not (lead.email or lead.phone or lead.linkedin_url):
        raise LeadError("A lead needs an email, phone or LinkedIn URL")


def add_note(db: Session, lead: Lead, body: str, user: User) -> LeadNote:
    """Add one entry to the lead's notes thread, signed with the author and time."""
    if not body or not body.strip():
        raise LeadError("A note cannot be empty")
    note = LeadNote(lead_id=lead.id, user_id=user.id, body=body.strip(),
                    created_at=utc_now(), author=user)
    db.add(note)
    db.flush()
    return note


def bulk_update(db: Session, leads: list[Lead], changes: dict, user: User) -> None:
    """Same change on many leads, one by one, so each lead gets its own history."""
    for lead in leads:
        update_lead(db, lead, changes, user)


def delete_lead(db: Session, lead: Lead) -> None:
    """Delete a junk lead. Its calls, status history and notes go with it (FK cascade)."""
    db.delete(lead)
    db.flush()


def bulk_delete(db: Session, leads: list[Lead]) -> None:
    for lead in leads:
        delete_lead(db, lead)

