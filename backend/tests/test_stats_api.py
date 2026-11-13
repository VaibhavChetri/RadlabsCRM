"""Phase 6: GET /stats/summary and GET /stats/team over HTTP."""

from datetime import date

from models import utc_now

IST = 330


def _today_ist() -> str:
    from datetime import timedelta
    return (utc_now() + timedelta(minutes=IST)).date().isoformat()


def _summary(client, headers, **params):
    today = _today_ist()
    query = {"scope": "me", "from": today, "to": today, "tz_offset": IST, **params}
    return client.get("/stats/summary", params=query, headers=headers)


def test_summary_counts_what_i_did_today(client, auth_headers):
    headers = auth_headers()
    lead = client.post("/leads", json={"first_name": "Ravi", "email": "ravi@acme.com",
                                       "source": "Apollo"}, headers=headers).json()
    client.post(f"/leads/{lead['uuid']}/call", headers=headers)
    client.patch(f"/leads/{lead['uuid']}", json={"status": "Meeting booked"}, headers=headers)

    res = _summary(client, headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cards"] == {
        "total_leads": 1, "leads_added": 1, "calls": 1, "follow_ups_due": 0,
        "meetings_booked": 1, "won": 0, "conversion_pct": 0.0,
    }
    assert body["calls_per_day"] == [{"date": _today_ist(), "count": 1}]
    assert body["added_per_day"] == [{"date": _today_ist(), "count": 1}]
    assert len(body["funnel"]) == 10
    assert {"status": "Meeting booked", "is_exit": False, "count": 1} in body["funnel"]
    assert {"source": "Apollo", "count": 1} in body["by_source"]


def test_team_stats_has_a_row_for_every_active_user(client, auth_headers):
    asha = auth_headers(name="Asha", email="asha@example.com")
    auth_headers(name="Vikram", email="vikram@example.com")
    lead = client.post("/leads", json={"first_name": "Ravi", "email": "ravi@acme.com"},
                       headers=asha).json()
    client.post(f"/leads/{lead['uuid']}/call", headers=asha)
    today = _today_ist()

    res = client.get("/stats/team", params={"from": today, "to": today, "tz_offset": IST},
                     headers=asha)

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["statuses"]) == 10
    rows = {row["name"]: row for row in body["rows"]}
    assert set(rows) == {"Asha", "Vikram"}
    assert rows["Asha"]["calls"] == 1 and rows["Asha"]["leads"] == 1
    assert rows["Asha"]["by_status"]["New"] == 1
    assert rows["Vikram"]["calls"] == 0


def test_stats_need_a_login(client):
    today = _today_ist()
    assert client.get("/stats/summary", params={"from": today, "to": today}).status_code == 401
    assert client.get("/stats/team", params={"from": today, "to": today}).status_code == 401


def test_a_bad_period_is_refused_with_a_clear_message(client, auth_headers):
    headers = auth_headers()

    backwards = _summary(client, headers, **{"from": "2026-11-10", "to": "2026-11-01"})
    too_long = client.get("/stats/team", params={"from": "2024-01-01", "to": "2026-11-01"},
                          headers=headers)

    assert backwards.status_code == 422
    assert backwards.json()["detail"] == "The start date must be on or before the end date"
    assert too_long.status_code == 422
    assert too_long.json()["detail"] == "Pick a period of 366 days or less"
    assert _summary(client, headers, scope="everyone").status_code == 422
    assert client.get("/stats/summary", headers=headers).status_code == 422  # no dates
