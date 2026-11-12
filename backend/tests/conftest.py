"""
Test setup.

A separate MySQL database (`<main db>_test`) is dropped and created fresh
for each test run. No mocks for the database. Tables are emptied between
tests; the seeded statuses stay.
"""

import os
import sys

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

_env = {**dotenv_values(os.path.join(BACKEND_DIR, ".env")), **os.environ}
_main_url = make_url(os.environ.get("TEST_DATABASE_URL") or _env["DATABASE_URL"])
TEST_DB_NAME = (
    _main_url.database
    if _main_url.database.endswith("_test")
    else f"{_main_url.database}_test"
)
TEST_URL = _main_url.set(database=TEST_DB_NAME)
SERVER_URL = _main_url.set(database=None)

# Must be set before the app modules are imported.
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)
os.environ.setdefault("SECRET_KEY", "test-secret")


def recreate_database(name: str) -> None:
    assert name.endswith("_test"), "refusing to drop a non-test database"
    server = create_engine(SERVER_URL)
    with server.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{name}`"))
        conn.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4"))
    server.dispose()


def drop_database(name: str) -> None:
    assert name.endswith("_test")
    server = create_engine(SERVER_URL)
    with server.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{name}`"))
    server.dispose()


def database_url(name: str) -> str:
    return _main_url.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    recreate_database(TEST_DB_NAME)
    from database import Base, SessionLocal, engine
    import models

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        models.seed_statuses(db)
        db.commit()
    yield
    engine.dispose()


KEEP_TABLES = {"statuses"}


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    from database import Base, engine

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in Base.metadata.sorted_tables:
            if table.name not in KEEP_TABLES:
                conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def db():
    """A session that sees rows committed by API calls made during the test."""
    from database import SessionLocal, engine

    bind = engine.execution_options(isolation_level="READ COMMITTED")
    with SessionLocal(bind=bind) as session:
        yield session


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db):
    """Create a user directly in the DB. Returns the User."""
    from auth import hash_password
    from models import User

    def _make(name="Asha", email="asha@example.com", password="secret123",
              role="member", is_active=True):
        user = User(name=name, email=email, password_hash=hash_password(password),
                    role=role, is_active=is_active)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_headers(client, make_user):
    """Log in as a fresh member and return the Authorization header."""

    def _headers(**kwargs):
        user = make_user(**kwargs)
        password = kwargs.get("password", "secret123")
        res = client.post("/auth/login", json={"email": user.email, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _headers
