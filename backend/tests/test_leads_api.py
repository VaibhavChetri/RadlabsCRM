from datetime import datetime, timedelta, timezone


def test_create_lead_returns_the_new_lead(client, auth_headers):
    headers = auth_headers(name="Asha")

    res = client.post(
        "/leads",
        json={"first_name": "Ravi", "last_name": "Kumar", "company": "Acme",
              "email": "ravi@acme.com", "phone": "+91 98765 43210"},
        headers=headers,
    )

    assert res.status_code == 201, res.text
    lead = res.json()
    assert len(lead["uuid"]) == 36
    assert "id" not in lead
    assert lead["first_name"] == "Ravi"
    assert lead["company"] == "Acme"
    assert lead["status"] == "New"
    assert lead["created_by"] == "Asha"
    assert lead["owner"] == "Asha"
    added = datetime.fromisoformat(lead["created_at"])
    assert added.tzinfo is not None  # UTC offset is sent, browser shows local time
    assert abs((datetime.now(timezone.utc) - added).total_seconds()) < 60


def test_create_lead_without_login_is_rejected(client):
    res = client.post("/leads", json={"first_name": "Ravi", "email": "ravi@acme.com"})
    assert res.status_code == 401


def test_old_public_submit_route_is_gone(client):
    res = client.post("/leads/submit", json={"client_id": "x", "name": "Spam"})
    assert res.status_code in (401, 404, 405)
    assert client.get("/leads/stats").status_code in (401, 404, 405)


def test_create_lead_needs_a_name(client, auth_headers):
    res = client.post("/leads", json={"email": "ravi@acme.com"}, headers=auth_headers())
    assert res.status_code == 422


def test_create_lead_needs_email_phone_or_linkedin(client, auth_headers):
    res = client.post("/leads", json={"first_name": "Ravi", "company": "Acme"},
                      headers=auth_headers())
    assert res.status_code == 422
    assert "email, phone or LinkedIn" in res.text


def test_list_leads_shows_all_leads_newest_first_with_added_info(client, auth_headers, db):
    from models import Lead

    asha = auth_headers(name="Asha", email="asha@example.com")
    vik = auth_headers(name="Vikram", email="vikram@example.com")
    client.post("/leads", json={"first_name": "Old", "email": "old@acme.com"}, headers=asha)
    client.post("/leads", json={"first_name": "Fresh", "phone": "9876543210"}, headers=vik)
    # Make the order unambiguous (DATETIME has 1-second precision).
    old = db.query(Lead).filter(Lead.first_name == "Old").one()
    old.created_at -= timedelta(hours=1)
    db.commit()

    res = client.get("/leads", headers=asha)

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert [lead["first_name"] for lead in body["items"]] == ["Fresh", "Old"]
    assert body["items"][0]["created_by"] == "Vikram"  # everyone sees all leads
    assert body["items"][0]["status"] == "New"
    assert body["items"][0]["created_at"]


def test_list_leads_without_login_is_rejected(client):
    assert client.get("/leads").status_code == 401


def test_adding_a_lead_that_already_exists_returns_409_with_the_existing_lead(client, auth_headers):
    headers = auth_headers()
    first = client.post("/leads", json={"first_name": "Ravi", "last_name": "Kumar",
                                        "email": "ravi@acme.com", "phone": "+91 98765 43210"},
                        headers=headers).json()

    for duplicate in ({"email": "RAVI@Acme.com"}, {"phone": "98765-43210"}):
        res = client.post("/leads", json={"first_name": "R", **duplicate}, headers=headers)
        assert res.status_code == 409, res.text
        assert res.json()["detail"] == {
            "message": "This lead is already in the CRM",
            "lead_uuid": first["uuid"],
            "name": "Ravi Kumar",
        }
    assert len(client.get("/leads", headers=headers).json()["items"]) == 1
