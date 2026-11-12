"""
schemas.py
----------
Shapes of data going in and out of the API.
Internal integer ids never appear here; only public uuids.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, EmailStr, PlainSerializer, field_validator, model_validator

from models import PRIORITIES, SOURCES, Lead


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    uuid: str
    name: str
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


# ---------- Leads ----------
def _as_utc(value: datetime) -> str:
    """DB times are naive UTC. Send them with an explicit UTC offset."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_as_utc, return_type=str)]

Source = Literal[SOURCES]
Priority = Literal[PRIORITIES]


class LeadCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_2: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    source: Source = "Other"
    priority: Priority = "warm"

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _name_and_contact_required(self):
        if not (self.first_name or self.last_name):
            raise ValueError("A lead needs a first or last name")
        if not (self.email or self.phone or self.linkedin_url):
            raise ValueError("A lead needs an email, phone or LinkedIn URL")
        return self


class LeadOut(BaseModel):
    uuid: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_2: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    source: str
    priority: str
    status: str
    owner: Optional[str] = None       # owner's name
    created_by: Optional[str] = None  # creator's name
    created_at: UTCDateTime           # "Added to CRM"
    updated_at: UTCDateTime

    @classmethod
    def from_lead(cls, lead: Lead) -> "LeadOut":
        data = {name: getattr(lead, name) for name in cls.model_fields
                if name not in ("status", "owner", "created_by")}
        return cls(
            **data,
            status=lead.status.name,
            owner=lead.owner.name if lead.owner else None,
            created_by=lead.creator.name if lead.creator else None,
        )


class LeadList(BaseModel):
    items: list[LeadOut]
    total: int
