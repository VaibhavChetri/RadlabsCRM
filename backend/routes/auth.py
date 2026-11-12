"""
routes/auth.py
--------------
The login endpoint.

POST /auth/login
    Body:     { "email": "...", "password": "..." }
    Returns:  { "access_token": "...", "token_type": "bearer" }

Flow:
  1. Look up the client by email.
  2. Verify the password against the stored bcrypt hash.
  3. If good, hand back a signed JWT token carrying their client_id.
  4. If bad, return 401 — and we deliberately DON'T say whether it was the
     email or the password that was wrong (don't help attackers).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Client
from schemas import LoginRequest, Token
from auth import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.email == credentials.email).first()

    if not client or not verify_password(credentials.password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(client_uuid=client.uuid)
    return Token(access_token=token)
