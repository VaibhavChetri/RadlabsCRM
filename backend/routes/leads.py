"""
routes/leads.py
---------------
All routes need a valid login. Leads are addressed by public uuid only.

POST   /leads          add one lead (manual form). 409 { message, lead_uuid, name } when
                       the person is already in the CRM (same email, phone or LinkedIn)
GET    /leads          the All-leads table -> { items, total }
                       ?q= search name, company, email, phone
                       &status= &owner= (uuid | unassigned) &source= &priority=
                         (repeat a filter for "any of these")
                       &added_from= &added_to= (local dates) &tz_offset= (minutes, IST = 330)
                       &sort= added | last_called | follow_up | priority | company
                       &order= asc | desc &page= (from 1) &page_size= (max 200)
GET    /leads/export   same filters and sort, every row, as .xlsx (incl. notes)
POST   /leads/bulk     { uuids, action: update | delete, changes: {status, owner_uuid, priority} }
                       all or nothing -> { count }
GET    /leads/today?today=YYYY-MM-DD   my call list -> { overdue, due_today, new }
GET    /leads/{uuid}        one lead with every field
PATCH  /leads/{uuid}        edit fields, status, owner, follow-up
DELETE /leads/{uuid}        delete (calls and history go with it)
POST   /leads/{uuid}/call   +1 Call
GET    /leads/{uuid}/notes  notes thread, newest first
POST   /leads/{uuid}/notes  add a note (signed with my name and the time)
"""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

import lead_export
import lead_query
import lead_service
from lead_matcher import LeadIndex
from auth import get_current_user
from database import get_db
from models import Lead, LeadNote, User, utc_now
from schemas import (
    BulkRequest, BulkResult, LeadCreate, LeadList, LeadOut, LeadUpdate, NoteCreate, NoteOut,
    Priority, Source, TodayList,
)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_id = LeadIndex.load(db).find(payload.model_dump())
    if existing_id is not None:
        existing = db.get(Lead, existing_id)
        name = " ".join(filter(None, [existing.first_name, existing.last_name]))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "message": "This lead is already in the CRM",
            "lead_uuid": existing.uuid,
            "name": name,
        })
    lead = lead_service.create_lead(db, payload.model_dump(), user)
    db.commit()
    db.refresh(lead)
    return LeadOut.from_lead(lead)


def lead_filters(
    q: str | None = None,
    status: list[str] = Query(default=[]),
    source: list[Source] = Query(default=[]),
    priority: list[Priority] = Query(default=[]),
    owner: list[str] = Query(default=[], description='user uuid, or "unassigned"'),
    added_from: date | None = None,
    added_to: date | None = None,
    tz_offset: int = Query(default=0, ge=-14 * 60, le=14 * 60,
                           description="local time minus UTC, in minutes (IST = 330)"),
) -> lead_query.LeadFilters:
    """Query-string filters shared by the table and its Excel export.
    A filter given several times (?status=New&status=Won) means any of them."""
    return lead_query.LeadFilters(
        q=q, statuses=status, sources=source, priorities=priority, owners=owner,
        added_from=added_from, added_to=added_to, tz_offset=tz_offset,
    )


def lead_sort(
    sort: Literal[tuple(lead_query.SORT_COLUMNS)] = "added",
    order: Literal["asc", "desc"] | None = None,
) -> lead_query.LeadSort:
    return lead_query.LeadSort(key=sort, order=order)


@router.get("", response_model=LeadList)
def list_leads(
    filters: lead_query.LeadFilters = Depends(lead_filters),
    sort: lead_query.LeadSort = Depends(lead_sort),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Everyone sees all leads."""
    leads, total = lead_query.search_leads(db, filters, sort, page, page_size)
    return LeadList(items=[LeadOut.from_lead(lead) for lead in leads], total=total)


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export")
def export_leads(
    filters: lead_query.LeadFilters = Depends(lead_filters),
    sort: lead_query.LeadSort = Depends(lead_sort),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every lead matching the table's filters (no paging), as .xlsx."""
    leads = lead_query.all_leads(db, filters, sort)
    notes = lead_query.notes_by_lead(db, filters)
    content = lead_export.leads_workbook(leads, notes, filters.tz_offset)
    local_today = (utc_now() + timedelta(minutes=filters.tz_offset)).date()
    return Response(
        content=content,
        media_type=XLSX_TYPE,
        headers={"Content-Disposition":
                 f'attachment; filename="radlabs-leads-{local_today.isoformat()}.xlsx"'},
    )


@router.post("/bulk", response_model=BulkResult)
def bulk_action(
    payload: BulkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set status / owner / priority on many leads, or delete them. All or nothing.
    The UI asks for confirmation before a bulk delete."""
    uuids = set(payload.uuids)
    leads = db.query(Lead).filter(Lead.uuid.in_(uuids)).all()
    if len(leads) < len(uuids):
        missing = len(uuids) - len(leads)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{missing} lead{'s' if missing > 1 else ''} not found. Nothing was changed.",
        )
    if payload.action == "delete":
        lead_service.bulk_delete(db, leads)
        db.commit()
        return BulkResult(count=len(leads))
    try:
        lead_service.bulk_update(db, leads, payload.changes.model_dump(exclude_unset=True), user)
    except lead_service.LeadError as err:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail=f"{err}. Nothing was changed.")
    db.commit()
    return BulkResult(count=len(leads))


# Declared before /{lead_uuid} so "today" is not read as a uuid.
@router.get("/today", response_model=TodayList)
def today_list(
    today: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """`today` is the caller's local date (the browser sends it)."""
    sections = lead_query.today_list(db, user, today)
    return TodayList(**{
        name: [LeadOut.from_lead(lead) for lead in leads]
        for name, leads in sections.items()
    })


def _get_lead_or_404(db: Session, lead_uuid: str) -> Lead:
    lead = db.query(Lead).filter(Lead.uuid == lead_uuid).first()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.get("/{lead_uuid}", response_model=LeadOut)
def get_lead(
    lead_uuid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return LeadOut.from_lead(_get_lead_or_404(db, lead_uuid))


@router.post("/{lead_uuid}/call", response_model=LeadOut)
def log_call(
    lead_uuid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = lead_service.log_call(db, _get_lead_or_404(db, lead_uuid), user)
    db.commit()
    db.refresh(lead)
    return LeadOut.from_lead(lead)


@router.patch("/{lead_uuid}", response_model=LeadOut)
def update_lead(
    lead_uuid: str,
    payload: LeadUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_uuid)
    try:
        lead_service.update_lead(db, lead, payload.model_dump(exclude_unset=True), user)
    except lead_service.LeadError as err:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err))
    db.commit()
    db.refresh(lead)
    return LeadOut.from_lead(lead)


@router.delete("/{lead_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_uuid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead_service.delete_lead(db, _get_lead_or_404(db, lead_uuid))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lead_uuid}/notes", response_model=list[NoteOut])
def list_notes(
    lead_uuid: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_uuid)
    notes = (
        db.query(LeadNote)
        .options(joinedload(LeadNote.author))
        .filter(LeadNote.lead_id == lead.id)
        .order_by(LeadNote.created_at.desc(), LeadNote.id.desc())
        .all()
    )
    return [NoteOut.from_note(note) for note in notes]


@router.post("/{lead_uuid}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    lead_uuid: str,
    payload: NoteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = _get_lead_or_404(db, lead_uuid)
    try:
        note = lead_service.add_note(db, lead, payload.body, user)
    except lead_service.LeadError as err:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err))
    db.commit()
    return NoteOut.from_note(note)
