"""
routes/lookups.py
-----------------
Small lists for dropdowns. Any logged-in user can read them.

GET /statuses   the 10 pipeline stages in order -> [{ name, sort_order, is_exit }]
GET /owners     active team members by name     -> [{ uuid, name }]
                (/users is the admin-only Team page API, Phase 7)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Status, User
from schemas import OwnerOut, StatusOut

router = APIRouter(tags=["lookups"], dependencies=[Depends(get_current_user)])


@router.get("/statuses", response_model=list[StatusOut])
def list_statuses(db: Session = Depends(get_db)):
    return db.query(Status).order_by(Status.sort_order).all()


@router.get("/owners", response_model=list[OwnerOut])
def list_owners(db: Session = Depends(get_db)):
    return db.query(User).filter(User.is_active.is_(True)).order_by(User.name).all()
