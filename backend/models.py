"""
models.py
---------
The CRM schema. This file is the single source of truth for the tables:
the migration and the test database are both built from it.

Rules:
  * Every table has an internal integer `id`. It never leaves the API.
  * Users and leads also have a public `uuid`. URLs and responses use it.
  * All times are stored as UTC (naive DATETIME holding UTC).
"""

import uuid as uuid_lib
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from database import Base

SOURCES = ("Apollo", "LinkedIn", "Referral", "Event", "Cold list", "Other")
PRIORITIES = ("hot", "warm", "cold")
ROLES = ("admin", "member")

# (name, is_exit) in pipeline order.
PIPELINE_STATUSES = [
    ("New", False),
    ("Attempted", False),
    ("Connected", False),
    ("Interested", False),
    ("Meeting booked", False),
    ("Proposal sent", False),
    ("Won", True),
    ("Lost", True),
    ("Not interested", True),
    ("Do not call", True),
]


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (what we store)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_uuid() -> str:
    return str(uuid_lib.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, default=new_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(*ROLES, name="user_role"), nullable=False, default="member")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Status(Base):
    __tablename__ = "statuses"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    sort_order = Column(Integer, nullable=False)
    is_exit = Column(Boolean, nullable=False, default=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, default=new_uuid)

    # Person
    first_name = Column(String(100))
    last_name = Column(String(100))
    job_title = Column(String(255))
    email = Column(String(255), index=True)
    phone = Column(String(50), index=True)
    phone_2 = Column(String(50))
    linkedin_url = Column(String(500), index=True)

    # Company
    company = Column(String(255))
    website = Column(String(500))
    industry = Column(String(255))
    company_size = Column(String(50))
    city = Column(String(100))
    country = Column(String(100))

    # Sales work
    source = Column(Enum(*SOURCES, name="lead_source"), nullable=False, default="Other")
    priority = Column(Enum(*PRIORITIES, name="lead_priority"), nullable=False, default="warm")
    status_id = Column(Integer, ForeignKey("statuses.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    call_attempts = Column(Integer, nullable=False, default=0)
    last_called_at = Column(DateTime)
    next_follow_up = Column(Date, index=True)

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)  # "Added to CRM"
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    status = relationship("Status")
    owner = relationship("User", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    called_at = Column(DateTime, nullable=False, default=utc_now, index=True)


class LeadNote(Base):
    """One entry in a lead's notes thread. Never edited; goes with the lead."""
    __tablename__ = "lead_notes"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    author = relationship("User")


class StatusChange(Base):
    __tablename__ = "status_changes"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status_id = Column(Integer, ForeignKey("statuses.id"), nullable=True)
    to_status_id = Column(Integer, ForeignKey("statuses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    changed_at = Column(DateTime, nullable=False, default=utc_now, index=True)


class ImportPreset(Base):
    __tablename__ = "import_presets"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    mapping = Column(JSON, nullable=False)  # file header -> CRM field
    is_builtin = Column(Boolean, nullable=False, default=False)


class Import(Base):
    __tablename__ = "imports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    source = Column(Enum(*SOURCES, name="import_source"), nullable=False)
    added = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    user = relationship("User")


def seed_statuses(db) -> None:
    """Insert the 10 pipeline stages if they are not there yet."""
    existing = {s.name for s in db.query(Status).all()}
    for order, (name, is_exit) in enumerate(PIPELINE_STATUSES, start=1):
        if name not in existing:
            db.add(Status(name=name, sort_order=order, is_exit=is_exit))
    db.flush()
