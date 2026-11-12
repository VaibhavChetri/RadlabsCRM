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


def test_save_notes_records_who_edited_and_when(db, make_user):
    creator = make_user(name="Asha", email="asha@example.com")
    editor = make_user(name="Vikram", email="vikram@example.com")
    lead = _new_lead(db, creator)
    before = utc_now() - timedelta(seconds=1)

    lead_service.save_notes(db, lead, "Call back after budget meeting", editor)
    db.commit()

    db.refresh(lead)
    assert lead.notes == "Call back after budget meeting"
    assert lead.notes_updated_by == editor.id
    assert lead.notes_updated_at >= before


def test_saving_unchanged_notes_keeps_the_last_editor(db, make_user):
    creator = make_user(name="Asha", email="asha@example.com")
    other = make_user(name="Vikram", email="vikram@example.com")
    lead = _new_lead(db, creator)
    lead_service.save_notes(db, lead, "Hello", creator)
    db.commit()

    lead_service.save_notes(db, lead, "Hello", other)
    db.commit()

    db.refresh(lead)
    assert lead.notes_updated_by == creator.id


def test_stamp_text_is_date_time_and_name_in_brackets():
    from datetime import datetime

    assert lead_service.stamp_text("Asha", datetime(2026, 11, 2, 9, 5)) == "[02 Nov 09:05 · Asha] "
    assert lead_service.stamp_text("Vikram Rao", datetime(2026, 1, 31, 18, 45)) == \
        "[31 Jan 18:45 · Vikram Rao] "
