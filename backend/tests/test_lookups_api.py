"""Lists that feed the lead page dropdowns: statuses and owners."""


def test_statuses_are_listed_in_pipeline_order_with_exit_flag(client, auth_headers):
    res = client.get("/statuses", headers=auth_headers())

    assert res.status_code == 200, res.text
    statuses = res.json()
    assert [s["name"] for s in statuses] == [
        "New", "Attempted", "Connected", "Interested", "Meeting booked",
        "Proposal sent", "Won", "Lost", "Not interested", "Do not call",
    ]
    assert [s["name"] for s in statuses if s["is_exit"]] == [
        "Won", "Lost", "Not interested", "Do not call",
    ]
    assert "id" not in statuses[0]


def test_owners_are_the_active_users_by_name(client, auth_headers, make_user):
    headers = auth_headers(name="Vikram", email="vikram@example.com")
    make_user(name="Asha", email="asha@example.com")
    make_user(name="Gone", email="gone@example.com", is_active=False)

    res = client.get("/owners", headers=headers)

    assert res.status_code == 200, res.text
    assert [o["name"] for o in res.json()] == ["Asha", "Vikram"]
    assert set(res.json()[0]) == {"uuid", "name"}


def test_lookups_need_a_login(client):
    assert client.get("/statuses").status_code == 401
    assert client.get("/owners").status_code == 401
