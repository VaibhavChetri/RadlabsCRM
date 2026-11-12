"""
models.py
---------
Python representations of our two MySQL tables. SQLAlchemy uses these
classes to turn rows into objects and back.

These MUST match `database/schema.sql`. The SQL file creates the tables;
these classes just map onto them.
"""

import uuid as uuid_lib

from sqlalchemy import (
    Column, Integer, String, Text, Enum, TIMESTAMP, ForeignKey, func
)
from sqlalchemy.orm import relationship
from database import Base


class Client(Base):
    __tablename__ = "clients"

    # `id` is the INTERNAL primary key. It stays as the fast integer link for
    # the leads foreign key, but it is NEVER sent out of the API.
    id = Column(Integer, primary_key=True, index=True)
    # `uuid` is the PUBLIC identifier — the only client id we ever expose.
    # A new random UUID is generated automatically when a client is created.
    uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid_lib.uuid4()),
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)   # login id + notify email
    password_hash = Column(String(255), nullable=False)        # bcrypt hash only
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Convenience: client.leads gives all that client's leads.
    leads = relationship("Lead", back_populates="client")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    message = Column(Text)
    status = Column(
        Enum("new", "contacted", "closed"),
        nullable=False,
        default="new",
    )
    submitted_at = Column(TIMESTAMP, server_default=func.now())

    # Convenience: lead.client gives the owning client.
    client = relationship("Client", back_populates="leads")
