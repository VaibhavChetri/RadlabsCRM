"""Team admin: /users routes (admin only), deactivation, reset, reassign."""

import pytest


@pytest.fixture
def admin_headers(auth_headers):
    return auth_headers(name="Admin", email="admin@example.com", role="admin")


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(res):
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_admin_adds_a_user_who_can_log_in_and_see_all_leads(client, admin_headers):
    client.post("/leads", headers=admin_headers,
                json={"first_name": "Ravi", "email": "ravi@acme.com"})

    res = client.post("/users", headers=admin_headers, json={
        "name": "Neha", "email": "neha@example.com",
        "password": "temp-pass-1", "role": "member",
    })

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Neha" and body["role"] == "member" and body["is_active"] is True
    assert "id" not in body and "password_hash" not in body

    logged_in = login(client, "neha@example.com", "temp-pass-1")
    assert logged_in.status_code == 200
    leads = client.get("/leads", headers=bearer(logged_in)).json()
    assert [lead["first_name"] for lead in leads["items"]] == ["Ravi"]


def test_a_member_gets_403_on_every_users_route(client, auth_headers, make_user):
    member = auth_headers(name="Asha", email="asha@example.com", role="member")
    other = make_user(name="Neha", email="neha@example.com")

    calls = [
        ("get", "/users", None),
        ("post", "/users", {"name": "X", "email": "x@example.com", "password": "password1"}),
        ("patch", f"/users/{other.uuid}", {"is_active": False}),
        ("post", f"/users/{other.uuid}/reset-password", {"password": "password1"}),
        ("post", f"/users/{other.uuid}/reassign-leads", {"to_uuid": None}),
    ]
    for method, url, body in calls:
        res = client.request(method, url, headers=member, json=body)
        assert res.status_code == 403, (method, url, res.status_code)


def test_users_routes_need_a_login(client):
    assert client.get("/users").status_code == 401


def test_deactivated_user_is_refused_at_login_and_their_old_token_gets_401(
        client, admin_headers, make_user):
    neha = make_user(name="Neha", email="neha@example.com", password="neha-pass-1")
    old_token = bearer(login(client, "neha@example.com", "neha-pass-1"))
    assert client.get("/leads", headers=old_token).status_code == 200

    res = client.patch(f"/users/{neha.uuid}", headers=admin_headers, json={"is_active": False})

    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    assert login(client, "neha@example.com", "neha-pass-1").status_code == 401
    assert client.get("/leads", headers=old_token).status_code == 401


def test_reactivated_user_can_log_in_again(client, admin_headers, make_user):
    neha = make_user(name="Neha", email="neha@example.com", password="neha-pass-1",
                     is_active=False)

    client.patch(f"/users/{neha.uuid}", headers=admin_headers, json={"is_active": True})

    assert login(client, "neha@example.com", "neha-pass-1").status_code == 200


def test_password_reset_works_and_the_old_password_stops_working(
        client, admin_headers, make_user):
    neha = make_user(name="Neha", email="neha@example.com", password="old-pass-1")

    res = client.post(f"/users/{neha.uuid}/reset-password", headers=admin_headers,
                      json={"password": "new-pass-1"})

    assert res.status_code == 204, res.text
    assert login(client, "neha@example.com", "old-pass-1").status_code == 401
    assert login(client, "neha@example.com", "new-pass-1").status_code == 200


def test_reset_password_refuses_a_short_password(client, admin_headers, make_user):
    neha = make_user(name="Neha", email="neha@example.com")

    res = client.post(f"/users/{neha.uuid}/reset-password", headers=admin_headers,
                      json={"password": "short"})

    assert res.status_code == 422


def _today_ist():
    from datetime import timedelta
    from models import utc_now
    return (utc_now() + timedelta(minutes=330)).date().isoformat()


def _team_row(client, headers, name):
    today = _today_ist()
    rows = client.get("/stats/team", headers=headers,
                      params={"from": today, "to": today, "tz_offset": 330}).json()["rows"]
    return next(r for r in rows if r["name"] == name)


def test_reassign_moves_all_their_leads_and_keeps_their_past_stats(
        client, admin_headers, make_user):
    make_user(name="Neha", email="neha@example.com", password="neha-pass-1")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    neha_headers = bearer(login(client, "neha@example.com", "neha-pass-1"))
    for i in range(3):
        lead = client.post("/leads", headers=neha_headers,
                           json={"first_name": f"Lead {i}", "email": f"l{i}@acme.com"}).json()
        client.post(f"/leads/{lead['uuid']}/call", headers=neha_headers)
    client.patch(f"/leads/{lead['uuid']}", headers=neha_headers, json={"status": "Won"})
    neha = next(u for u in client.get("/users", headers=admin_headers).json()
                if u["name"] == "Neha")
    client.patch(f"/users/{neha['uuid']}", headers=admin_headers, json={"is_active": False})

    res = client.post(f"/users/{neha['uuid']}/reassign-leads", headers=admin_headers,
                      json={"to_uuid": vikram.uuid})

    assert res.status_code == 200, res.text
    assert res.json() == {"count": 3}
    leads = client.get("/leads", headers=admin_headers).json()["items"]
    assert {lead["owner"] for lead in leads} == {"Vikram"}
    past = _team_row(client, admin_headers, "Neha")
    assert (past["calls"], past["won"], past["is_active"]) == (3, 1, False)
    assert past["leads"] == 0
    assert _team_row(client, admin_headers, "Vikram")["leads"] == 3


def test_reassign_to_unassigned_clears_the_owner(client, admin_headers, make_user):
    make_user(name="Neha", email="neha@example.com", password="neha-pass-1")
    neha_headers = bearer(login(client, "neha@example.com", "neha-pass-1"))
    client.post("/leads", headers=neha_headers, json={"first_name": "Ravi", "email": "r@a.com"})
    neha = next(u for u in client.get("/users", headers=admin_headers).json()
                if u["name"] == "Neha")

    res = client.post(f"/users/{neha['uuid']}/reassign-leads", headers=admin_headers,
                      json={"to_uuid": None})

    assert res.json() == {"count": 1}
    assert client.get("/leads", headers=admin_headers).json()["items"][0]["owner"] is None


def test_reassign_to_a_deactivated_user_is_refused_and_moves_nothing(
        client, admin_headers, make_user):
    make_user(name="Neha", email="neha@example.com", password="neha-pass-1")
    gone = make_user(name="Gone", email="gone@example.com", is_active=False)
    neha_headers = bearer(login(client, "neha@example.com", "neha-pass-1"))
    client.post("/leads", headers=neha_headers, json={"first_name": "Ravi", "email": "r@a.com"})
    neha = next(u for u in client.get("/users", headers=admin_headers).json()
                if u["name"] == "Neha")

    res = client.post(f"/users/{neha['uuid']}/reassign-leads", headers=admin_headers,
                      json={"to_uuid": gone.uuid})

    assert res.status_code == 400
    assert client.get("/leads", headers=admin_headers).json()["items"][0]["owner"] == "Neha"


def test_adding_a_user_with_an_email_already_used_returns_409(client, admin_headers, make_user):
    make_user(name="Neha", email="neha@example.com")

    res = client.post("/users", headers=admin_headers, json={
        "name": "Neha 2", "email": "Neha@Example.com", "password": "temp-pass-1",
    })

    assert res.status_code == 409
    assert res.json()["detail"] == "A user with this email already exists"


def test_add_user_needs_a_name_and_a_long_enough_password(client, admin_headers):
    for body in ({"name": " ", "email": "a@example.com", "password": "temp-pass-1"},
                 {"name": "A", "email": "a@example.com", "password": "short"},
                 {"name": "A", "email": "not-an-email", "password": "temp-pass-1"}):
        assert client.post("/users", headers=admin_headers, json=body).status_code == 422


def test_admin_cannot_deactivate_or_demote_themselves(client, admin_headers):
    me = client.get("/auth/me", headers=admin_headers).json()

    for change in ({"is_active": False}, {"role": "member"}):
        res = client.patch(f"/users/{me['uuid']}", headers=admin_headers, json=change)
        assert res.status_code == 400, change

    assert client.get("/auth/me", headers=admin_headers).status_code == 200


def test_list_shows_everyone_active_first_with_leads_owned(client, admin_headers, make_user):
    make_user(name="Zara", email="zara@example.com", password="zara-pass-1")
    make_user(name="Bala", email="bala@example.com", is_active=False)
    zara_headers = bearer(login(client, "zara@example.com", "zara-pass-1"))
    client.post("/leads", headers=zara_headers, json={"first_name": "Ravi", "email": "r@a.com"})

    res = client.get("/users", headers=admin_headers)

    assert res.status_code == 200, res.text
    users = res.json()
    assert [(u["name"], u["is_active"], u["leads"]) for u in users] == [
        ("Admin", True, 0), ("Zara", True, 1), ("Bala", False, 0),
    ]
    assert set(users[0]) == {"uuid", "name", "email", "role", "is_active", "created_at", "leads"}


def test_promoting_a_member_to_admin_gives_access_at_once(client, admin_headers, make_user):
    make_user(name="Neha", email="neha@example.com", password="neha-pass-1")
    neha_headers = bearer(login(client, "neha@example.com", "neha-pass-1"))
    assert client.get("/users", headers=neha_headers).status_code == 403
    neha = next(u for u in client.get("/users", headers=admin_headers).json()
                if u["name"] == "Neha")

    client.patch(f"/users/{neha['uuid']}", headers=admin_headers, json={"role": "admin"})

    assert client.get("/users", headers=neha_headers).status_code == 200


def test_unknown_user_uuid_returns_404(client, admin_headers):
    res = client.patch("/users/not-a-uuid", headers=admin_headers, json={"name": "X"})
    assert res.status_code == 404


def test_deactivated_users_are_not_offered_as_owners(client, admin_headers, make_user):
    neha = make_user(name="Neha", email="neha@example.com")

    client.patch(f"/users/{neha.uuid}", headers=admin_headers, json={"is_active": False})

    assert [o["name"] for o in client.get("/owners", headers=admin_headers).json()] == ["Admin"]
