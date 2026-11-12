"""
create_test_client.py
----------------------
Inserts ONE test client into the `clients` table so we have an account
to log in with while building/testing the system.

WHY A SCRIPT (and not plain SQL)?
    A client's password must be stored as a bcrypt *hash*, never as plain
    text. We cannot type a bcrypt hash by hand, so this little script:
        1. hashes the password with passlib (same library auth.py uses),
        2. inserts the client row into MySQL.

WHEN TO RUN IT:
    Run this AFTER Step 2, once you've created the virtual environment and
    run `pip install -r backend/requirements.txt` (that installs passlib,
    bcrypt and pymysql which this script needs).

HOW TO RUN IT (from the project root, with the venv active):
    python database/create_test_client.py

It reads the database connection from backend/.env so there is only ONE
place that holds the DB credentials.
"""

import os
import uuid as uuid_lib
from passlib.hash import bcrypt
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ---- The test account you'll log in with -------------------------------
TEST_CLIENT_NAME = "Test Client"
TEST_CLIENT_EMAIL = "Radlabs@leads.com"
TEST_CLIENT_PASSWORD = "Radlabs123"          # plain text ONLY here; stored hashed
# ------------------------------------------------------------------------

# Load DATABASE_URL from backend/.env (single source of truth).
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit(
        "DATABASE_URL not found. Make sure backend/.env exists (created in Step 2)."
    )

engine = create_engine(DATABASE_URL)

# Turn the plain password into a bcrypt hash.
password_hash = bcrypt.hash(TEST_CLIENT_PASSWORD)

with engine.begin() as conn:
    # Don't create the same test client twice.
    existing = conn.execute(
        text("SELECT id FROM clients WHERE email = :email"),
        {"email": TEST_CLIENT_EMAIL},
    ).first()

    if existing:
        row = conn.execute(
            text("SELECT uuid FROM clients WHERE email = :email"),
            {"email": TEST_CLIENT_EMAIL},
        ).first()
        print("Test client already exists. Nothing to do.")
        print(f"   email: {TEST_CLIENT_EMAIL}")
        print(f"   uuid:  {row[0]}   <-- use this as client_id when submitting leads")
    else:
        new_uuid = str(uuid_lib.uuid4())
        conn.execute(
            text(
                "INSERT INTO clients (uuid, name, email, password_hash) "
                "VALUES (:uuid, :name, :email, :password_hash)"
            ),
            {
                "uuid": new_uuid,
                "name": TEST_CLIENT_NAME,
                "email": TEST_CLIENT_EMAIL,
                "password_hash": password_hash,
            },
        )
        print("✅ Test client created!")
        print(f"   email:    {TEST_CLIENT_EMAIL}")
        print(f"   password: {TEST_CLIENT_PASSWORD}")
        print(f"   uuid:     {new_uuid}   <-- use this as client_id when submitting leads")
