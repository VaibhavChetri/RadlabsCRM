"""
schemas.py
----------
Pydantic models = the "shape" of data going IN and OUT of the API.

- Request schemas validate what the caller sends (e.g. login needs an
  email + password).
- Response schemas control what we send back (e.g. we NEVER send the
  password hash out).

Lead-related schemas are added in Step 3 when we build the leads routes.
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr


# ---------- Auth ----------
class LoginRequest(BaseModel):
    """Body of POST /auth/login — matches the React form (JSON)."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """What /auth/login returns."""
    access_token: str
    token_type: str = "bearer"


# ---------- Clients ----------
class ClientCreate(BaseModel):
    """Body of POST /clients/create."""
    name: str
    email: EmailStr
    password: str


class ClientOut(BaseModel):
    """
    Safe client info to send back. We expose the public `uuid` as the client's
    id and NEVER the internal integer primary key (no password either).
    """
    uuid: str
    name: str
    email: EmailStr

    class Config:
        from_attributes = True   # lets us build this straight from a DB object


# ---------- Leads ----------
class LeadSubmit(BaseModel):
    """
    Body of POST /leads/submit — sent by a client's website contact form.
    This endpoint is PUBLIC, so the form must tell us which client the lead
    belongs to via client_id. That id is now the client's PUBLIC UUID (a
    string), not the internal number. Only client_id and name are required;
    the rest are optional because forms often collect different fields.
    """
    client_id: str          # the client's public UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None


class LeadOut(BaseModel):
    """
    The shape of a lead we send BACK to the dashboard (GET /leads/).
    These are exactly the columns the leads table on screen will show.
    """
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    status: str
    submitted_at: datetime

    class Config:
        from_attributes = True   # build straight from a DB Lead object


class LeadStatusUpdate(BaseModel):
    """
    Body of PATCH /leads/{id}/status. Literal means only these exact values
    are accepted — anything else is auto-rejected with a 422 error.
    """
    status: Literal["new", "contacted", "closed"]
