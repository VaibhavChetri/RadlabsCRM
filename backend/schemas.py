"""
schemas.py
----------
Shapes of data going in and out of the API.
Internal integer ids never appear here; only public uuids.
"""

from datetime import date, datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, field_validator, model_validator

from import_engine import FIELDS as IMPORT_FIELDS
from models import PRIORITIES, ROLES, SOURCES, Lead


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


# ---------- Dropdown lists ----------
class StatusOut(BaseModel):
    name: str
    sort_order: int
    is_exit: bool

    model_config = {"from_attributes": True}


class OwnerOut(BaseModel):
    uuid: str
    name: str

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


class _PersonAndCompany(BaseModel):
    """The lead fields a person types in. Blank text is stored as NULL."""
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

    @field_validator(
        "first_name", "last_name", "job_title", "email", "phone", "phone_2",
        "linkedin_url", "company", "website", "industry", "company_size", "city",
        "country", mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class LeadCreate(_PersonAndCompany):
    source: Source = "Other"
    priority: Priority = "warm"

    @model_validator(mode="after")
    def _name_and_contact_required(self):
        if not (self.first_name or self.last_name):
            raise ValueError("A lead needs a first or last name")
        if not (self.email or self.phone or self.linkedin_url):
            raise ValueError("A lead needs an email, phone or LinkedIn URL")
        return self


class LeadUpdate(_PersonAndCompany):
    """PATCH body: only the fields that are sent are changed."""
    source: Optional[Source] = None
    priority: Optional[Priority] = None
    status: Optional[str] = None
    owner_uuid: Optional[str] = None  # null = Unassigned
    next_follow_up: Optional[date] = None  # null = no follow-up


# LeadOut fields built from relationships, not copied from a column.
_RELATED_FIELDS = ("status", "owner", "owner_uuid", "created_by")


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
    owner_uuid: Optional[str] = None
    call_attempts: int
    last_called_at: Optional[UTCDateTime] = None
    next_follow_up: Optional[date] = None
    created_by: Optional[str] = None  # creator's name
    created_at: UTCDateTime           # "Added to CRM"
    updated_at: UTCDateTime

    @classmethod
    def from_lead(cls, lead: Lead) -> "LeadOut":
        data = {name: getattr(lead, name) for name in cls.model_fields
                if name not in _RELATED_FIELDS}
        return cls(
            **data,
            status=lead.status.name,
            owner=lead.owner.name if lead.owner else None,
            owner_uuid=lead.owner.uuid if lead.owner else None,
            created_by=lead.creator.name if lead.creator else None,
        )


class LeadList(BaseModel):
    items: list[LeadOut]
    total: int


class BulkChanges(BaseModel):
    """What a bulk update may set. Only the fields that are sent are changed."""
    status: Optional[str] = None
    owner_uuid: Optional[str] = None  # null = Unassigned
    priority: Optional[Priority] = None


class BulkRequest(BaseModel):
    uuids: list[str] = Field(min_length=1, max_length=5000)
    action: Literal["update", "delete"]
    changes: Optional[BulkChanges] = None  # needed for "update"

    @model_validator(mode="after")
    def _update_needs_a_change(self):
        if self.action == "update" and not (self.changes and self.changes.model_fields_set):
            raise ValueError("Choose a status, owner or priority to set")
        return self


class BulkResult(BaseModel):
    count: int  # leads changed or deleted


class TodayList(BaseModel):
    """Home-screen call list, in the order the caller works it."""
    overdue: list[LeadOut]    # follow-up date before today
    due_today: list[LeadOut]  # follow-up date is today
    new: list[LeadOut]        # status New, no follow-up due yet


# ---------- Team admin (/users) ----------
Role = Literal[ROLES]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: Password  # temporary password the admin hands over
    role: Role = "member"

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class TeamUserOut(BaseModel):
    uuid: str
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: UTCDateTime
    leads: int = 0  # leads they own now


class UserUpdate(BaseModel):
    """PATCH body: only the fields that are sent are changed."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[Role] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class PasswordReset(BaseModel):
    password: Password


class ReassignRequest(BaseModel):
    to_uuid: Optional[str]  # an active user, or null = Unassigned


class ReassignResult(BaseModel):
    count: int  # leads moved


# ---------- Notes thread ----------
class NoteCreate(BaseModel):
    body: str


class NoteOut(BaseModel):
    author: str
    body: str
    created_at: UTCDateTime

    @classmethod
    def from_note(cls, note) -> "NoteOut":
        return cls(author=note.author.name, body=note.body, created_at=note.created_at)


# ---------- Import ----------
class ImportRowOut(BaseModel):
    row: int      # row number in the file (the header is row 1)
    result: Literal["added", "updated", "skipped"]
    reason: str = ""
    values: list[str] = []  # the row as it is in the file
    name: str = ""          # the person's name as mapped
    filled: list[str] = []  # updated rows: the CRM fields that were empty and got filled


class ImportReport(BaseModel):
    import_uuid: str = ""  # use with GET /leads?import= to list the leads it added
    added: int
    updated: int
    skipped: int
    headers: list[str]  # the file's columns, in order (for `values`)
    rows: list[ImportRowOut]


class ImportPreview(BaseModel):
    file_name: str
    headers: list[str]
    row_count: int                     # data rows (blank rows not counted)
    sample_rows: list[list[str]]       # first rows, as in the file
    mapping: dict[str, Optional[str]]  # file header -> CRM field, None = skip
    preset: Optional[str] = None       # name of the preset the mapping came from
    mapped_rows: list[dict[str, str]]  # first rows as they will look in the CRM


ImportField = Literal[IMPORT_FIELDS]
ImportMapping = dict[str, Optional[ImportField]]  # file header -> CRM field, None = skip


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mapping: ImportMapping

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class PresetOut(BaseModel):
    name: str
    mapping: ImportMapping
    is_builtin: bool

    model_config = {"from_attributes": True}


class ImportOut(BaseModel):
    """One line of the import history."""
    file_name: str
    source: str
    user: str  # who ran it
    added: int
    updated: int
    skipped: int
    created_at: UTCDateTime

    @classmethod
    def from_import(cls, record) -> "ImportOut":
        return cls(file_name=record.file_name, source=record.source, user=record.user.name,
                   added=record.added, updated=record.updated, skipped=record.skipped,
                   created_at=record.created_at)


# ---------- Stats ----------
class StatsCards(BaseModel):
    total_leads: int
    leads_added: int
    calls: int
    follow_ups_due: int
    meetings_booked: int
    won: int
    conversion_pct: Optional[float]  # None when no leads were added in the period


class DayCount(BaseModel):
    date: date  # the user's local date
    count: int


class FunnelStage(BaseModel):
    status: str
    is_exit: bool
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class StatsSummary(BaseModel):
    cards: StatsCards
    funnel: list[FunnelStage]          # all 10 stages, pipeline order
    calls_per_day: list[DayCount]      # every day of the period, 0 when none
    added_per_day: list[DayCount]
    by_source: list[SourceCount]       # every source


class TeamRow(BaseModel):
    uuid: str
    name: str
    is_active: bool
    calls: int
    meetings_booked: int
    won: int
    leads: int                    # leads they own now
    by_status: dict[str, int]     # those leads by current status


class TeamStats(BaseModel):
    statuses: list[str]  # column order
    rows: list[TeamRow]
