"""Phase 3: GET /leads/today, the caller's home-screen call list."""

TODAY = "2026-11-12"


def _add_lead(client, headers, first_name="Ravi", **fields):
    body = {"first_name": first_name, "email": f"{first_name.lower()}@acme.com", **fields}
    res = client.post("/leads", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _today(client, headers, today=TODAY):
    res = client.get("/leads/today", params={"today": today}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _names(rows):
    return [row["first_name"] for row in rows]


def test_my_new_lead_is_in_the_new_section(client, auth_headers):
    headers = auth_headers()
    _add_lead(client, headers, first_name="Ravi")

    body = _today(client, headers)

    assert _names(body["new"]) == ["Ravi"]
    assert body["overdue"] == []
    assert body["due_today"] == []


def _set(client, headers, lead, **changes):
    res = client.patch(f"/leads/{lead['uuid']}", json=changes, headers=headers)
    assert res.status_code == 200, res.text


def test_follow_ups_are_split_into_overdue_and_due_today(client, auth_headers):
    headers = auth_headers()
    late = _add_lead(client, headers, first_name="Late")
    _set(client, headers, late, status="Attempted", next_follow_up="2026-11-10")
    due = _add_lead(client, headers, first_name="Due")
    _set(client, headers, due, status="Interested", next_follow_up=TODAY)
    later = _add_lead(client, headers, first_name="Later")
    _set(client, headers, later, status="Connected", next_follow_up="2026-11-20")

    body = _today(client, headers)

    assert _names(body["overdue"]) == ["Late"]
    assert _names(body["due_today"]) == ["Due"]
    assert body["new"] == []


def test_a_new_lead_with_a_follow_up_due_is_listed_once(client, auth_headers):
    headers = auth_headers()
    late = _add_lead(client, headers, first_name="Late")
    _set(client, headers, late, next_follow_up="2026-11-01")
    due = _add_lead(client, headers, first_name="Due")
    _set(client, headers, due, next_follow_up=TODAY)
    later = _add_lead(client, headers, first_name="Later")
    _set(client, headers, later, next_follow_up="2026-11-30")

    body = _today(client, headers)

    assert _names(body["overdue"]) == ["Late"]
    assert _names(body["due_today"]) == ["Due"]
    assert _names(body["new"]) == ["Later"]


def test_exit_status_leads_are_left_out(client, auth_headers):
    headers = auth_headers()
    for name, status in [("Won", "Won"), ("Lost", "Lost"), ("Nope", "Not interested"),
                         ("Dnc", "Do not call")]:
        for follow_up in ("2026-11-01", TODAY):
            lead = _add_lead(client, headers, first_name=f"{name}{follow_up[-2:]}")
            _set(client, headers, lead, status=status, next_follow_up=follow_up)

    body = _today(client, headers)

    assert body == {"overdue": [], "due_today": [], "new": []}


def test_only_my_leads_are_listed(client, auth_headers):
    asha = auth_headers(name="Asha", email="asha@example.com")
    vikram = auth_headers(name="Vikram", email="vikram@example.com")
    _add_lead(client, asha, first_name="Mine")
    theirs = _add_lead(client, vikram, first_name="Theirs")
    _set(client, vikram, theirs, next_follow_up=TODAY)
    nobody = _add_lead(client, asha, first_name="Nobody")
    _set(client, asha, nobody, owner_uuid=None, next_follow_up=TODAY)

    body = _today(client, asha)

    assert _names(body["new"]) == ["Mine"]
    assert body["overdue"] == [] and body["due_today"] == []


def test_each_section_is_sorted_for_calling(client, auth_headers, db):
    from datetime import timedelta
    from models import Lead

    headers = auth_headers()
    # overdue: oldest follow-up first, then Hot -> Warm -> Cold on the same day
    for name, follow_up, priority in [("O3", "2026-11-11", "hot"), ("O2", "2026-11-05", "cold"),
                                      ("O1", "2026-11-05", "hot")]:
        lead = _add_lead(client, headers, first_name=name)
        _set(client, headers, lead, next_follow_up=follow_up, priority=priority)
    # due today: Hot -> Warm -> Cold
    for name, priority in [("Tc", "cold"), ("Th", "hot"), ("Tw", "warm")]:
        lead = _add_lead(client, headers, first_name=name)
        _set(client, headers, lead, next_follow_up=TODAY, priority=priority)
    # new: Hot -> Warm -> Cold, oldest added first on the same priority
    for name, priority in [("Nw", "warm"), ("Nh2", "hot"), ("Nc", "cold"), ("Nh1", "hot")]:
        lead = _add_lead(client, headers, first_name=name, priority=priority)
    # DATETIME has 1-second precision: make "added" order unambiguous.
    nh1 = db.query(Lead).filter(Lead.first_name == "Nh1").one()
    nh1.created_at -= timedelta(days=1)
    db.commit()

    body = _today(client, headers)

    assert _names(body["overdue"]) == ["O1", "O2", "O3"]
    assert _names(body["due_today"]) == ["Th", "Tw", "Tc"]
    assert _names(body["new"]) == ["Nh1", "Nh2", "Nw", "Nc"]


def test_today_list_needs_a_login_and_a_valid_date(client, auth_headers):
    assert client.get("/leads/today", params={"today": TODAY}).status_code == 401

    headers = auth_headers()
    assert client.get("/leads/today", headers=headers).status_code == 422
    assert client.get("/leads/today", params={"today": "soon"}, headers=headers).status_code == 422
