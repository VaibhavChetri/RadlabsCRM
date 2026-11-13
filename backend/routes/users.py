"""
routes/users.py
---------------
The Team admin API. Admin only: members get 403 on every route.
Users are addressed by public uuid.

GET   /users                           everyone (active and deactivated), with leads owned
POST  /users                           { name, email, password, role } -> the new user (201)
                                       409 when the email is already used
PATCH /users/{uuid}                    { name, role, is_active } (only what is sent)
                                       an admin cannot deactivate or demote themselves
POST  /users/{uuid}/reset-password     { password }  the old password stops working
POST  /users/{uuid}/reassign-leads     { to_uuid | null }  move all their leads -> { count }

A deactivated user cannot log in, and their old token is refused (auth.get_current_user).
Their leads, calls and status history stay, so past stats do not change.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import lead_service
from auth import hash_password, require_admin
from database import get_db
from models import Lead, User
from schemas import (
    PasswordReset, ReassignRequest, ReassignResult, TeamUserOut, UserCreate, UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def _leads_owned(db: Session) -> dict[int, int]:
    rows = db.query(Lead.owner_id, func.count(Lead.id)).group_by(Lead.owner_id).all()
    return {owner_id: count for owner_id, count in rows if owner_id is not None}


def _out(user: User, leads: int = 0) -> TeamUserOut:
    return TeamUserOut(uuid=user.uuid, name=user.name, email=user.email, role=user.role,
                       is_active=user.is_active, created_at=user.created_at, leads=leads)


def _get_user(db: Session, user_uuid: str) -> User:
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _owned_count(db: Session, user: User) -> int:
    return db.query(func.count(Lead.id)).filter(Lead.owner_id == user.id).scalar()


@router.get("", response_model=list[TeamUserOut])
def list_users(db: Session = Depends(get_db)):
    """Active people first, then by name."""
    owned = _leads_owned(db)
    users = db.query(User).order_by(User.is_active.desc(), User.name).all()
    return [_out(u, owned.get(u.id, 0)) for u in users]


@router.post("", response_model=TeamUserOut, status_code=status.HTTP_201_CREATED)
def add_user(payload: UserCreate, db: Session = Depends(get_db)):
    # The email column compares without case, so this also catches "Neha@..." vs "neha@...".
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="A user with this email already exists")
    user = User(name=payload.name, email=payload.email,
                password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/{user_uuid}", response_model=TeamUserOut)
def update_user(
    user_uuid: str,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_uuid)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "role", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be empty")

    if user.id == admin.id and (changes.get("is_active") is False
                                or changes.get("role") == "member"):
        # Keeps at least one admin who can get back in.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You cannot deactivate or demote your own account")

    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _out(user, _owned_count(db, user))


@router.post("/{user_uuid}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_uuid: str, payload: PasswordReset, db: Session = Depends(get_db)):
    user = _get_user(db, user_uuid)
    user.password_hash = hash_password(payload.password)
    db.commit()


@router.post("/{user_uuid}/reassign-leads", response_model=ReassignResult)
def reassign_leads(
    user_uuid: str,
    payload: ReassignRequest,
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_uuid)
    try:
        count = lead_service.reassign_leads(db, user, payload.to_uuid)
    except lead_service.LeadError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    return ReassignResult(count=count)
