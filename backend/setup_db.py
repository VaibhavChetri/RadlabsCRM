"""
setup_db.py
-----------
Set up an EMPTY database (first deploy to a new server). Safe to run again:
it never deletes or changes existing rows.

  1. Create all tables from models.py.
  2. Seed the 10 pipeline statuses and the built-in import formats.
  3. Create the first logins from INITIAL_USERS, skipping emails that exist.

INITIAL_USERS is a JSON list, for example:
    [{"name": "Radlabs Admin", "email": "admin@x.com", "role": "admin",
      "password": "a-long-password"}]

Run from backend/:
    DATABASE_URL=... SECRET_KEY=... INITIAL_USERS='[...]' python setup_db.py
"""

import json
import os

import import_engine
import models
from auth import hash_password
from database import Base, SessionLocal, engine

MIN_PASSWORD_LENGTH = 12


def load_users() -> list[dict]:
    users = json.loads(os.getenv("INITIAL_USERS", "[]"))
    for u in users:
        if u.get("role") not in models.ROLES:
            raise ValueError(f"Bad role for {u.get('email')}: {u.get('role')}")
        if len(u.get("password", "")) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password for {u.get('email')} is too short")
    return users


def run() -> None:
    users = load_users()
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        models.seed_statuses(db)
        import_engine.seed_builtin_presets(db)

        created = []
        for u in users:
            exists = db.query(models.User).filter(models.User.email == u["email"]).first()
            if exists:
                continue
            db.add(models.User(
                name=u["name"],
                email=u["email"],
                role=u["role"],
                password_hash=hash_password(u["password"]),
            ))
            created.append(u["email"])
        db.commit()

        statuses = db.query(models.Status).count()
        total_users = db.query(models.User).count()

    print(f"Tables ready. Statuses: {statuses}. Users: {total_users}. New logins: {len(created)}.")


if __name__ == "__main__":
    run()
