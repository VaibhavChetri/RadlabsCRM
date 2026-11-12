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
