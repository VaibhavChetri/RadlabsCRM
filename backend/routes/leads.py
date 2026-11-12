"""
routes/leads.py
---------------
All routes need a valid login. Leads are addressed by public uuid only.

POST /leads   add one lead (manual form)
GET  /leads   all leads, newest first -> { items, total }
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, joinedload

import lead_service
from auth import get_current_user
from database import get_db
from models import Lead, User
from schemas import LeadCreate, LeadList, LeadOut

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
