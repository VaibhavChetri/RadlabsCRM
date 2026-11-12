"""Lead matcher / merger: find the existing lead for a candidate, fill blanks only."""

import lead_service
from lead_matcher import LeadIndex


def _lead(db, user, **fields):
    lead = lead_service.create_lead(db, {"first_name": "Ravi", **fields}, user)
    db.commit()
    return lead


def test_email_matches_ignoring_case_and_spaces(db, make_user):
    user = make_user()
    ravi = _lead(db, user, email="Ravi@Acme.com")
    _lead(db, user, email="meera@globex.io")

    index = LeadIndex.load(db)

    assert index.find({"email": "  ravi@ACME.com "}) == ravi.id
    assert index.find({"email": "someone@else.com"}) is None


def test_phone_matches_on_the_last_10_digits(db, make_user):
    user = make_user()
    arjun = _lead(db, user, phone="+91 98765-43210")

    index = LeadIndex.load(db)

    assert index.find({"phone": "098765 43210"}) == arjun.id
    assert index.find({"phone": "(987) 654-3210"}) == arjun.id
    assert index.find({"phone": "98765 43211"}) is None
    assert index.find({"phone": "n/a"}) is None
    assert index.find({"phone": "43210"}) is None  # too short to trust


def test_linkedin_url_matches_without_scheme_www_query_or_trailing_slash(db, make_user):
    user = make_user()
    meera = _lead(db, user, linkedin_url="https://www.linkedin.com/in/Meera-Shah/")

    index = LeadIndex.load(db)

    assert index.find({"linkedin_url": "linkedin.com/in/meera-shah"}) == meera.id
    assert index.find({"linkedin_url": "http://linkedin.com/in/meera-shah?trk=abc"}) == meera.id
    assert index.find({"linkedin_url": "https://linkedin.com/in/meera-s"}) is None


def test_match_order_is_email_then_phone_then_linkedin(db, make_user):
    user = make_user()
    by_email = _lead(db, user, email="ravi@acme.com")
    by_phone = _lead(db, user, phone="9876543210")
    by_linkedin = _lead(db, user, linkedin_url="linkedin.com/in/ravi")

    index = LeadIndex.load(db)

    everything = {"email": "ravi@acme.com", "phone": "9876543210",
                  "linkedin_url": "linkedin.com/in/ravi"}
    assert index.find(everything) == by_email.id
    assert index.find({**everything, "email": "new@acme.com"}) == by_phone.id
    assert index.find({**everything, "email": None, "phone": "1112223334"}) == by_linkedin.id


def test_merge_fills_empty_fields_only_and_never_protected_ones(db, make_user):
    from lead_matcher import fields_to_fill

    user = make_user()
    lead = _lead(db, user, email="ravi@acme.com", company="Acme", phone=None)

    fills = fields_to_fill(lead, {
        "email": "ravi@acme.com", "company": "Acme Corp", "phone": "9876543210",
        "city": "Pune", "job_title": "",
        "status_id": 99, "owner_id": 99, "priority": "hot", "call_attempts": 7,
        "next_follow_up": "2026-12-01", "source": "Apollo",
    })

    assert fills == {"phone": "9876543210", "city": "Pune"}
