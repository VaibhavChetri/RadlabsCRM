"""
database.py
-----------
The one place that knows how to talk to MySQL.

- `engine`      : connection pool.
- `SessionLocal`: hands out one DB session per request.
- `Base`        : parent class of every table model (models.py is the
                  single source of truth for the schema).
- `get_db()`    : FastAPI dependency; opens a session and always closes it.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

# pool_pre_ping: MySQL drops idle connections; check before use.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
