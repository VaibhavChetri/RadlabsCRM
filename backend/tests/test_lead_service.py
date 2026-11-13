from datetime import timedelta

import lead_service
from models import Lead, StatusChange, utc_now


def test_create_lead_starts_as_new_and_writes_first_status_change(db, make_user):
    user = make_user()
    before = utc_now() - timedelta(seconds=1)

    lead = lead_service.create_lead(
        db, {"first_name": "Ravi", "company": "Acme", "email": "ravi@acme.com"}, user
    )
    db.commit()

    saved = db.query(Lead).filter(Lead.uuid == lead.uuid).one()
    assert saved.status.name == "New"
    assert saved.created_by == user.id
    assert saved.owner_id == user.id
    assert saved.created_at >= before

    changes = db.query(StatusChange).filter(StatusChange.lead_id == saved.id).all()
    assert len(changes) == 1
    assert changes[0].from_status_id is None
    assert changes[0].to_status_id == saved.status_id
    assert changes[0].user_id == user.id


def _new_lead(db, user, **fields):
    lead = lead_service.create_lead(db, {"first_name": "Ravi", "email": "ravi@acme.com", **fields}, user)
    db.commit()
    return lead


def test_log_call_counts_the_call_sets_last_called_and_writes_a_call_row(db, make_user):
    from models import Call

    user = make_user()
    lead = _new_lead(db, user)
    before = utc_now() - timedelta(seconds=1)

    lead_service.log_call(db, lead, user)
    lead_service.log_call(db, lead, user)
    db.commit()

    db.refresh(lead)
    assert lead.call_attempts == 2
    assert lead.last_called_at >= before
    calls = db.query(Call).filter(Call.lead_id == lead.id).all()
    assert len(calls) == 2
    assert all(c.user_id == user.id for c in calls)
    assert calls[-1].called_at == lead.last_called_at


def test_change_status_writes_history_with_from_to_user_and_time(db, make_user):
    from models import Status

    creator = make_user(name="Asha", email="asha@example.com")
    caller = make_user(name="Vikram", email="vikram@example.com")
    lead = _new_lead(db, creator)
    new = db.query(Status).filter(Status.name == "New").one()
    before = utc_now() - timedelta(seconds=1)

    lead_service.change_status(db, lead, "Interested", caller)
    db.commit()

    db.refresh(lead)
    assert lead.status.name == "Interested"
    last = (db.query(StatusChange).filter(StatusChange.lead_id == lead.id)
            .order_by(StatusChange.id.desc()).first())
    assert last.from_status_id == new.id
    assert last.to_status_id == lead.status_id
    assert last.user_id == caller.id
    assert last.changed_at >= before


def test_change_status_to_the_same_status_writes_no_history(db, make_user):
    user = make_user()
    lead = _new_lead(db, user)

    lead_service.change_status(db, lead, "New", user)
    db.commit()

    assert db.query(StatusChange).filter(StatusChange.lead_id == lead.id).count() == 1


def test_add_note_keeps_text_author_and_time(db, make_user):
    from models import LeadNote

    asha = make_user(name="Asha", email="asha@example.com")
    lead = _new_lead(db, asha)
    before = utc_now() - timedelta(seconds=1)

    lead_service.add_note(db, lead, "Wants a demo after Diwali", asha)
    db.commit()

    notes = db.query(LeadNote).filter(LeadNote.lead_id == lead.id).all()
    assert len(notes) == 1
    assert notes[0].body == "Wants a demo after Diwali"
    assert notes[0].user_id == asha.id
    assert notes[0].created_at >= before


def test_an_empty_note_is_refused(db, make_user):
    import pytest

    user = make_user()
    lead = _new_lead(db, user)

    with pytest.raises(lead_service.LeadError):
        lead_service.add_note(db, lead, "   \n ", user)


# ---------- Priority follows the status ----------
import pytest


@pytest.mark.parametrize("status", ["Interested", "Meeting booked", "Proposal sent"])
def test_showing_interest_makes_the_lead_hot(db, make_user, status):
    user = make_user()
    lead = _new_lead(db, user, priority="cold")

    lead_service.change_status(db, lead, status, user)
    db.commit()

    db.refresh(lead)
    assert lead.priority == "hot"


@pytest.mark.parametrize("status", ["Won", "Lost", "Not interested", "Do not call"])
def test_a_closed_lead_becomes_cold(db, make_user, status):
    user = make_user()
    lead = _new_lead(db, user, priority="hot")

    lead_service.change_status(db, lead, status, user)
    db.commit()

    db.refresh(lead)
    assert lead.priority == "cold"


@pytest.mark.parametrize("before, after", [("cold", "warm"), ("warm", "warm"), ("hot", "hot")])
def test_connected_makes_the_lead_at_least_warm(db, make_user, before, after):
    user = make_user()
    lead = _new_lead(db, user, priority=before)

    lead_service.change_status(db, lead, "Connected", user)
    db.commit()

    db.refresh(lead)
    assert lead.priority == after


@pytest.mark.parametrize("status", ["Attempted", "New"])
def test_no_conversation_yet_keeps_the_priority(db, make_user, status):
    user = make_user()
    lead = _new_lead(db, user, priority="hot")
    lead_service.change_status(db, lead, "Attempted", user)  # so "New" is a real move back

    lead_service.change_status(db, lead, status, user)
    db.commit()

    db.refresh(lead)
    assert lead.priority == "hot"


def test_a_priority_chosen_in_the_same_edit_wins(db, make_user):
    user = make_user()
    lead = _new_lead(db, user, priority="warm")

    lead_service.update_lead(db, lead, {"status": "Interested", "priority": "warm"}, user)
    db.commit()

    db.refresh(lead)
    assert (lead.status.name, lead.priority) == ("Interested", "warm")
