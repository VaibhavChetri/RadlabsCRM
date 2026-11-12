"""Phase 4: GET /leads with search, filters, sort and paging."""


def _add_lead(client, headers, first_name="Ravi", **fields):
    body = {"first_name": first_name, "email": f"{first_name.lower()}@example.com", **fields}
    res = client.post("/leads", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _list(client, headers, **params):
    res = client.get("/leads", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _names(body):
    return sorted(row["first_name"] for row in body["items"])


def test_search_matches_name_company_email_or_phone(client, auth_headers):
    headers = auth_headers()
    _add_lead(client, headers, first_name="Ravi", last_name="Kumar", company="Acme")
    _add_lead(client, headers, first_name="Meera", company="Globex", email="meera@globex.io")
    _add_lead(client, headers, first_name="Arjun", company="Initech", phone="+91 98765 43210")

    assert _names(_list(client, headers, q="kumar")) == ["Ravi"]
    assert _names(_list(client, headers, q="Ravi Kumar")) == ["Ravi"]
    assert _names(_list(client, headers, q="GLOBEX")) == ["Meera"]
    assert _names(_list(client, headers, q="meera@glo")) == ["Meera"]
    assert _names(_list(client, headers, q="9876543210")) == ["Arjun"]  # digits only
    body = _list(client, headers, q="nobody")
    assert body == {"items": [], "total": 0}


def _set(client, headers, lead, **changes):
    res = client.patch(f"/leads/{lead['uuid']}", json=changes, headers=headers)
    assert res.status_code == 200, res.text


def test_status_source_and_priority_filters_combine(client, auth_headers):
    headers = auth_headers()
    a = _add_lead(client, headers, first_name="A", source="Apollo", priority="hot")
    _set(client, headers, a, status="Interested")
    _add_lead(client, headers, first_name="B", source="Apollo", priority="cold")
    c = _add_lead(client, headers, first_name="C", source="Referral", priority="hot")
    _set(client, headers, c, status="Interested")
    _add_lead(client, headers, first_name="D", source="Referral", priority="hot")

    assert _names(_list(client, headers, status="Interested")) == ["A", "C"]
    assert _names(_list(client, headers, source="Apollo")) == ["A", "B"]
    assert _names(_list(client, headers, priority="hot")) == ["A", "C", "D"]
    assert _names(_list(client, headers, status="Interested", source="Referral")) == ["C"]
    # Several values of one filter mean "any of them".
    assert _names(_list(client, headers, status=["New", "Interested"], priority="cold")) == ["B"]
    assert _list(client, headers, priority="hot", q="D")["total"] == 1


def test_unknown_filter_values_are_refused(client, auth_headers):
    headers = auth_headers()
    assert client.get("/leads", params={"source": "Fax"}, headers=headers).status_code == 422
    assert client.get("/leads", params={"priority": "boiling"}, headers=headers).status_code == 422


def test_owner_filter_includes_unassigned(client, auth_headers, db):
    from models import User

    asha = auth_headers(name="Asha", email="asha@example.com")
    vikram = auth_headers(name="Vikram", email="vikram@example.com")
    _add_lead(client, asha, first_name="Mine")
    _add_lead(client, vikram, first_name="Theirs")
    nobody = _add_lead(client, asha, first_name="Nobody")
    _set(client, asha, nobody, owner_uuid=None)
    vikram_uuid = db.query(User).filter(User.name == "Vikram").one().uuid

    assert _names(_list(client, asha, owner=vikram_uuid)) == ["Theirs"]
    assert _names(_list(client, asha, owner="unassigned")) == ["Nobody"]
    assert _names(_list(client, asha, owner=["unassigned", vikram_uuid])) == ["Nobody", "Theirs"]


def _set_added(db, first_name, utc_time):
    from models import Lead

    lead = db.query(Lead).filter(Lead.first_name == first_name).one()
    lead.created_at = utc_time
    db.commit()


def test_date_added_range_uses_the_users_local_date(client, auth_headers, db):
    from datetime import datetime

    headers = auth_headers()
    for name in ("Before", "Early", "Late", "After"):
        _add_lead(client, headers, first_name=name)
    # IST is UTC+5:30 (tz_offset=330 minutes).
    _set_added(db, "Before", datetime(2026, 11, 9, 18, 0))   # 9 Nov 23:30 IST
    _set_added(db, "Early", datetime(2026, 11, 9, 18, 30))   # 10 Nov 00:00 IST
    _set_added(db, "Late", datetime(2026, 11, 11, 18, 29))   # 11 Nov 23:59 IST
    _set_added(db, "After", datetime(2026, 11, 11, 18, 30))  # 12 Nov 00:00 IST

    ist = {"tz_offset": 330}
    assert _names(_list(client, headers, added_from="2026-11-10", added_to="2026-11-11",
                        **ist)) == ["Early", "Late"]
    assert _names(_list(client, headers, added_from="2026-11-12", **ist)) == ["After"]
    assert _names(_list(client, headers, added_to="2026-11-09", **ist)) == ["Before"]
    # Without an offset the dates are UTC dates.
    assert _names(_list(client, headers, added_from="2026-11-10", added_to="2026-11-11")) \
        == ["After", "Late"]


def _ordered(body):
    return [row["first_name"] for row in body["items"]]


def test_sort_by_each_column_both_ways_with_blanks_last(client, auth_headers, db):
    from datetime import datetime

    headers = auth_headers()
    a = _add_lead(client, headers, first_name="A", company="Zeta", priority="cold")
    b = _add_lead(client, headers, first_name="B", company="alpha", priority="hot")
    _add_lead(client, headers, first_name="C", priority="warm")  # no company, never called
    _set(client, headers, a, next_follow_up="2026-11-20")
    _set(client, headers, b, next_follow_up="2026-11-15")
    client.post(f"/leads/{a['uuid']}/call", headers=headers)
    _set_added(db, "A", datetime(2026, 11, 1))
    _set_added(db, "B", datetime(2026, 11, 3))
    _set_added(db, "C", datetime(2026, 11, 2))

    def order(sort, direction):
        return _ordered(_list(client, headers, sort=sort, order=direction))

    assert _ordered(_list(client, headers)) == ["B", "C", "A"]  # default: newest added first
    assert order("added", "asc") == ["A", "C", "B"]
    assert order("company", "asc") == ["B", "A", "C"]   # case-insensitive, blank last
    assert order("company", "desc") == ["A", "B", "C"]
    assert order("follow_up", "asc") == ["B", "A", "C"]
    assert order("follow_up", "desc") == ["A", "B", "C"]
    assert order("last_called", "desc") == ["A", "B", "C"]
    assert order("last_called", "asc") == ["A", "B", "C"]
    assert order("priority", "asc") == ["B", "C", "A"]  # hot -> warm -> cold
    assert order("priority", "desc") == ["A", "C", "B"]
    assert client.get("/leads", params={"sort": "shoe_size"}, headers=headers).status_code == 422


def test_paging_returns_one_page_and_the_full_total(client, auth_headers):
    headers = auth_headers()
    for i in range(1, 6):
        _add_lead(client, headers, first_name=f"L{i}", company=f"Co{i}")

    def page(n):
        return _list(client, headers, sort="company", page=n, page_size=2)

    assert [_ordered(page(n)) for n in (1, 2, 3)] == [["L1", "L2"], ["L3", "L4"], ["L5"]]
    assert page(3)["total"] == 5
    assert page(4) == {"items": [], "total": 5}
    assert client.get("/leads", params={"page": 0}, headers=headers).status_code == 422
    assert client.get("/leads", params={"page_size": 1000}, headers=headers).status_code == 422


def test_table_stays_fast_with_thousands_of_leads(client, auth_headers, db):
    import time
    from datetime import datetime, timedelta
    from models import Lead, Status, User

    headers = auth_headers()
    owner = db.query(User).one()
    statuses = [s.id for s in db.query(Status).order_by(Status.sort_order)]
    start = datetime(2026, 1, 1)
    db.bulk_insert_mappings(Lead, [
        {"uuid": f"00000000-0000-0000-0000-{i:012d}", "first_name": f"Lead{i}",
         "company": f"Company {i % 300}", "email": f"lead{i}@example.com",
         "phone": f"98{i:08d}", "priority": ("hot", "warm", "cold")[i % 3],
         "source": "Apollo", "status_id": statuses[i % 10], "owner_id": owner.id,
         "created_by": owner.id, "created_at": start + timedelta(minutes=i),
         "updated_at": start, "call_attempts": 0,
         "next_follow_up": (start + timedelta(days=i % 60)).date() if i % 2 else None}
        for i in range(6000)
    ])
    db.commit()

    for params in [{}, {"sort": "company", "page": 40}, {"sort": "follow_up", "order": "desc"},
                   {"q": "Company 12", "priority": "hot"}, {"status": "New", "page": 5},
                   {"q": "9800001"}]:
        began = time.perf_counter()
        body = _list(client, headers, **params)
        elapsed = time.perf_counter() - began
        assert body["total"] > 0, params
        assert elapsed < 0.5, (params, elapsed)
    assert _list(client, headers)["total"] == 6000


def test_search_treats_percent_and_underscore_as_plain_text(client, auth_headers):
    headers = auth_headers()
    _add_lead(client, headers, first_name="Plain", company="AB Corp")
    _add_lead(client, headers, first_name="Under", company="A_B Corp")

    assert _names(_list(client, headers, q="A_B")) == ["Under"]
    assert _list(client, headers, q="%")["total"] == 0
