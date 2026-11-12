"""
database.py
-----------
ONE place that knows how to talk to MySQL.

- `engine`      : the actual connection pool to MySQL.
- `SessionLocal`: a factory that hands out short-lived DB "sessions"
                  (one per request).
- `Base`        : the parent class all our table models inherit from.
- `get_db()`    : a FastAPI dependency that opens a session for a request
                  and always closes it afterwards.

NOTE: The tables themselves are created by `database/schema.sql` (Step 1),
which is our single source of truth for the table design. This file only
*connects* to them.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Read backend/.env so DATABASE_URL is available.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Check backend/.env")

# pool_pre_ping=True quietly checks a connection is still alive before using
# it (MySQL drops idle connections); saves you from random errors.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """Open a DB session for one request, then close it no matter what."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
