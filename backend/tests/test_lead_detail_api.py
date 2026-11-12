"""Phase 2: the lead detail page API (get, edit, status, +1 call, notes, delete)."""


def _add_lead(client, headers, **fields):
    body = {"first_name": "Ravi", "email": "ravi@acme.com", **fields}
    res = client.post("/leads", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_get_lead_returns_every_field(client, auth_headers):
    headers = auth_headers(name="Asha")
    created = _add_lead(client, headers, last_name="Kumar", job_title="CTO",
                        phone="+91 98765 43210", linkedin_url="https://linkedin.com/in/ravi",
                        company="Acme", website="acme.com", city="Pune", country="India")

    res = client.get(f"/leads/{created['uuid']}", headers=headers)

    assert res.status_code == 200, res.text
    lead = res.json()
    assert lead["uuid"] == created["uuid"]
    assert "id" not in lead
    assert lead["job_title"] == "CTO"
    assert lead["linkedin_url"] == "https://linkedin.com/in/ravi"
    assert lead["status"] == "New"
    assert lead["owner"] == "Asha"
    assert len(lead["owner_uuid"]) == 36
    assert lead["call_attempts"] == 0
    assert lead["last_called_at"] is None
    assert lead["next_follow_up"] is None
    assert lead["notes"] is None
    assert lead["notes_updated_by"] is None


def test_get_unknown_lead_is_404(client, auth_headers):
    res = client.get("/leads/00000000-0000-0000-0000-000000000000", headers=auth_headers())
    assert res.status_code == 404


def test_plus_one_call_counts_the_call(client, auth_headers):
    headers = auth_headers()
    lead = _add_lead(client, headers)

    res = client.post(f"/leads/{lead['uuid']}/call", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["call_attempts"] == 1
    assert res.json()["last_called_at"] is not None


def test_patch_status_moves_the_lead_and_logs_history(client, auth_headers, db):
    from models import Lead, StatusChange

    headers = auth_headers()
    lead = _add_lead(client, headers)

    res = client.patch(f"/leads/{lead['uuid']}", json={"status": "Connected"}, headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "Connected"
    saved = db.query(Lead).filter(Lead.uuid == lead["uuid"]).one()
    assert db.query(StatusChange).filter(StatusChange.lead_id == saved.id).count() == 2


def test_patch_unknown_status_is_422(client, auth_headers):
    headers = auth_headers()
    lead = _add_lead(client, headers)

    res = client.patch(f"/leads/{lead['uuid']}", json={"status": "Maybe"}, headers=headers)

    assert res.status_code == 422
    assert "Unknown status" in res.text


def test_patch_fields_saves_them_and_bumps_updated_at(client, auth_headers, db):
    from datetime import timedelta
    from models import Lead

    headers = auth_headers()
    lead = _add_lead(client, headers)
    saved = db.query(Lead).filter(Lead.uuid == lead["uuid"]).one()
    saved.updated_at -= timedelta(hours=1)  # DATETIME has 1-second precision
    db.commit()
    old_updated_at = saved.updated_at

    res = client.patch(
        f"/leads/{lead['uuid']}",
        json={"job_title": "  Head of Sales ", "phone_2": "022 1234 5678", "industry": "SaaS",
              "company_size": "51-200", "priority": "hot", "source": "Referral",
              "email": ""},
        headers=headers,
    )
    # email "" would leave no contact info -> keep a phone so the edit is valid
    assert res.status_code == 422

    res = client.patch(
        f"/leads/{lead['uuid']}",
        json={"job_title": "  Head of Sales ", "phone_2": "022 1234 5678", "industry": "SaaS",
              "company_size": "51-200", "priority": "hot", "source": "Referral",
              "phone": "9876543210", "email": ""},
        headers=headers,
    )

    assert res.status_code == 200, res.text
    body = client.get(f"/leads/{lead['uuid']}", headers=headers).json()
    assert body["job_title"] == "Head of Sales"
    assert body["phone_2"] == "022 1234 5678"
    assert body["industry"] == "SaaS"
    assert body["company_size"] == "51-200"
    assert body["priority"] == "hot"
    assert body["source"] == "Referral"
    assert body["email"] is None
    assert body["first_name"] == "Ravi"  # not sent, not changed
    db.expire_all()
    assert db.query(Lead).filter(Lead.uuid == lead["uuid"]).one().updated_at > old_updated_at


def test_patch_owner_hands_over_or_unassigns_the_lead(client, auth_headers, make_user):
    headers = auth_headers(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    lead = _add_lead(client, headers)

    res = client.patch(f"/leads/{lead['uuid']}", json={"owner_uuid": vikram.uuid}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["owner"] == "Vikram"
    assert res.json()["owner_uuid"] == vikram.uuid

    res = client.patch(f"/leads/{lead['uuid']}", json={"owner_uuid": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["owner"] is None


def test_patch_owner_must_be_an_active_user(client, auth_headers, make_user):
    headers = auth_headers()
    gone = make_user(name="Gone", email="gone@example.com", is_active=False)
    lead = _add_lead(client, headers)

    for owner_uuid in (gone.uuid, "00000000-0000-0000-0000-000000000000"):
        res = client.patch(f"/leads/{lead['uuid']}", json={"owner_uuid": owner_uuid},
                           headers=headers)
        assert res.status_code == 422, owner_uuid


def test_patch_next_follow_up_saves_and_clears(client, auth_headers):
    headers = auth_headers()
    lead = _add_lead(client, headers)
    url = f"/leads/{lead['uuid']}"

    res = client.patch(url, json={"next_follow_up": "2026-11-20"}, headers=headers)
    assert res.status_code == 200, res.text
    assert client.get(url, headers=headers).json()["next_follow_up"] == "2026-11-20"

    res = client.patch(url, json={"next_follow_up": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert client.get(url, headers=headers).json()["next_follow_up"] is None


def test_patch_notes_shows_last_edited_by(client, auth_headers):
    headers = auth_headers(name="Asha")
    lead = _add_lead(client, headers)

    res = client.patch(f"/leads/{lead['uuid']}", json={"notes": "Wants a demo in Dec"},
                       headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["notes"] == "Wants a demo in Dec"
    assert body["notes_updated_by"] == "Asha"
    assert body["notes_updated_at"] is not None


def test_stamp_uses_my_name_and_my_local_time(client, auth_headers):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    import lead_service

    headers = auth_headers(name="Asha")

    res = client.get("/leads/stamp", params={"tz": "Asia/Kolkata"}, headers=headers)

    assert res.status_code == 200, res.text
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    # The minute may tick over between the request and this line.
    assert res.json()["text"] in {
        lead_service.stamp_text("Asha", now_ist),
        lead_service.stamp_text("Asha", now_ist - timedelta(minutes=1)),
    }


def test_stamp_with_a_bad_timezone_is_422(client, auth_headers):
    res = client.get("/leads/stamp", params={"tz": "Mars/Base"}, headers=auth_headers())
    assert res.status_code == 422


def test_delete_removes_the_lead_with_its_calls_and_history(client, auth_headers, db):
    from models import Call, Lead, StatusChange

    headers = auth_headers()
    lead = _add_lead(client, headers)
    client.post(f"/leads/{lead['uuid']}/call", headers=headers)
    client.patch(f"/leads/{lead['uuid']}", json={"status": "Attempted"}, headers=headers)
    lead_id = db.query(Lead).filter(Lead.uuid == lead["uuid"]).one().id

    res = client.delete(f"/leads/{lead['uuid']}", headers=headers)

    assert res.status_code == 204, res.text
    assert client.get(f"/leads/{lead['uuid']}", headers=headers).status_code == 404
    assert db.query(Call).filter(Call.lead_id == lead_id).count() == 0
    assert db.query(StatusChange).filter(StatusChange.lead_id == lead_id).count() == 0


def test_a_failed_patch_changes_nothing(client, auth_headers, db):
    from models import Lead, StatusChange

    headers = auth_headers()
    lead = _add_lead(client, headers)

    res = client.patch(
        f"/leads/{lead['uuid']}",
        json={"status": "Interested", "company": "NewCo", "owner_uuid": "no-such-user"},
        headers=headers,
    )

    assert res.status_code == 422
    body = client.get(f"/leads/{lead['uuid']}", headers=headers).json()
    assert body["status"] == "New"
    assert body["company"] is None
    saved = db.query(Lead).filter(Lead.uuid == lead["uuid"]).one()
    assert db.query(StatusChange).filter(StatusChange.lead_id == saved.id).count() == 1


def test_lead_detail_routes_need_a_login(client):
    url = "/leads/00000000-0000-0000-0000-000000000000"
    assert client.get(url).status_code == 401
    assert client.patch(url, json={"status": "Won"}).status_code == 401
    assert client.delete(url).status_code == 401
    assert client.post(f"{url}/call").status_code == 401
    assert client.get("/leads/stamp").status_code == 401
