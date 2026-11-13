"""Phase 4: POST /leads/bulk — change or delete many leads at once."""


def _add_leads(client, headers, *names):
    leads = []
    for name in names:
        res = client.post("/leads", json={"first_name": name, "email": f"{name.lower()}@example.com"},
                          headers=headers)
        assert res.status_code == 201, res.text
        leads.append(res.json())
    return leads


def _bulk(client, headers, **body):
    return client.post("/leads/bulk", json=body, headers=headers)


def test_bulk_status_change_writes_history_for_every_lead(client, auth_headers, db):
    from models import Lead, Status, StatusChange

    headers = auth_headers(name="Asha")
    a, b, untouched = _add_leads(client, headers, "A", "B", "C")

    res = _bulk(client, headers, uuids=[a["uuid"], b["uuid"]], action="update",
                changes={"status": "Interested"})

    assert res.status_code == 200, res.text
    assert res.json() == {"count": 2}
    interested = db.query(Status).filter(Status.name == "Interested").one()
    for lead in (a, b):
        row = db.query(Lead).filter(Lead.uuid == lead["uuid"]).one()
        assert row.status_id == interested.id
        changes = db.query(StatusChange).filter(StatusChange.lead_id == row.id,
                                                StatusChange.to_status_id == interested.id).all()
        assert len(changes) == 1
        assert changes[0].from_status_id is not None  # from New
    assert client.get(f"/leads/{untouched['uuid']}", headers=headers).json()["status"] == "New"


def test_bulk_update_is_all_or_nothing(client, auth_headers):
    headers = auth_headers()
    a, b = _add_leads(client, headers, "A", "B")
    ids = [a["uuid"], b["uuid"]]

    missing = _bulk(client, headers, uuids=[*ids, "no-such-lead"], action="update",
                    changes={"priority": "hot"})
    bad_status = _bulk(client, headers, uuids=ids, action="update", changes={"status": "Maybe"})
    bad_owner = _bulk(client, headers, uuids=ids, action="update",
                      changes={"priority": "hot", "owner_uuid": "no-such-user"})
    nothing = _bulk(client, headers, uuids=ids, action="update", changes={})

    assert missing.status_code == 404
    assert "1 lead" in missing.json()["detail"]
    assert bad_status.status_code == 422
    assert bad_owner.status_code == 422
    assert nothing.status_code == 422
    for lead in (a, b):
        now = client.get(f"/leads/{lead['uuid']}", headers=headers).json()
        assert (now["status"], now["priority"], now["owner"]) == ("New", "warm", lead["owner"])


def test_bulk_delete_removes_the_leads_with_their_history(client, auth_headers, db):
    from models import Call, Lead, LeadNote, StatusChange

    headers = auth_headers(role="admin")
    a, b, kept = _add_leads(client, headers, "A", "B", "Kept")
    client.post(f"/leads/{a['uuid']}/call", headers=headers)
    client.post(f"/leads/{b['uuid']}/notes", json={"body": "Junk import"}, headers=headers)

    res = _bulk(client, headers, uuids=[a["uuid"], b["uuid"]], action="delete")

    assert res.status_code == 200, res.text
    assert res.json() == {"count": 2}
    assert [lead.first_name for lead in db.query(Lead).all()] == ["Kept"]
    kept_id = db.query(Lead).one().id
    assert db.query(Call).count() == 0 and db.query(LeadNote).count() == 0
    assert {row.lead_id for row in db.query(StatusChange)} == {kept_id}
    assert client.get(f"/leads/{a['uuid']}", headers=headers).status_code == 404


def test_status_change_sets_the_priority_on_the_lead_page_and_in_bulk(client, auth_headers):
    headers = auth_headers()
    one, two, three = _add_leads(client, headers, "One", "Two", "Three")

    res = client.patch(f"/leads/{one['uuid']}", json={"status": "Meeting booked"}, headers=headers)
    assert res.json()["priority"] == "hot"

    _bulk(client, headers, uuids=[two["uuid"], three["uuid"]], action="update",
          changes={"status": "Not interested"})
    for lead in (two, three):
        assert client.get(f"/leads/{lead['uuid']}", headers=headers).json()["priority"] == "cold"
