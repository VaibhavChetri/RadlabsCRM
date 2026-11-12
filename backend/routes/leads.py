"""
routes/leads.py
---------------
All routes need a valid login. Leads are addressed by public uuid only.

POST   /leads          add one lead (manual form)
GET    /leads          all leads, newest first -> { items, total }
GET    /leads/{uuid}        one lead with every field
PATCH  /leads/{uuid}        edit fields, status, owner, follow-up
DELETE /leads/{uuid}        delete (calls and history go with it)
POST   /leads/{uuid}/call   +1 Call
GET    /leads/{uuid}/notes  notes thread, newest first
POST   /leads/{uuid}/notes  add a note (signed with my name and the time)
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

import lead_service
from auth import get_current_user
from database import get_db
from models import Lead, LeadNote, User
from schemas import LeadCreate, LeadList, LeadOut, LeadUpdate, NoteCreate, NoteOut

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = lead_service.create_lead(db, payload.model_dump(), user)
    db.commit()
    db.refresh(lead)
    return LeadOut.from_lead(lead)


@router.get("", response_model=LeadList)
def list_leads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Everyone sees all leads. Search, filters and paging come in Phase 4.
    leads = (
        db.query(Lead)
        .options(joinedload(Lead.status), joinedload(Lead.owner), joinedload(Lead.creator))
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .all()
    )
    return LeadList(items=[LeadOut.from_lead(lead) for lead in leads], total=len(leads))


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
