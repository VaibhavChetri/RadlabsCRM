from jose import jwt


def test_login_returns_token_with_user_uuid_and_role(client, make_user):
    user = make_user(email="ravi@example.com", password="pass1234", role="admin")

    res = client.post("/auth/login", json={"email": "ravi@example.com", "password": "pass1234"})

    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    claims = jwt.get_unverified_claims(body["access_token"])
    assert claims["sub"] == user.uuid
    assert claims["role"] == "admin"


def test_login_with_wrong_password_is_refused_with_clear_message(client, make_user):
    make_user(email="ravi@example.com", password="pass1234")

    res = client.post("/auth/login", json={"email": "ravi@example.com", "password": "nope"})

    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_login_with_unknown_email_gets_the_same_message(client):
    res = client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})

    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password"


def test_inactive_user_is_refused_at_login(client, make_user):
    make_user(email="left@example.com", password="pass1234", is_active=False)

    res = client.post("/auth/login", json={"email": "left@example.com", "password": "pass1234"})

    assert res.status_code == 401


def test_me_returns_the_logged_in_user(client, auth_headers):
    headers = auth_headers(name="Asha", email="asha@example.com")

    res = client.get("/auth/me", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Asha"
    assert body["email"] == "asha@example.com"
    assert body["role"] == "member"
    assert "id" not in body and "password_hash" not in body


def test_me_without_token_is_rejected(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_is_rejected(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert res.status_code == 401


def test_token_stops_working_once_user_is_deactivated(client, auth_headers, db):
    from models import User

    headers = auth_headers(email="soon-gone@example.com")
    user = db.query(User).filter(User.email == "soon-gone@example.com").one()
    user.is_active = False
    db.commit()

    assert client.get("/auth/me", headers=headers).status_code == 401
