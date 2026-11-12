"""
auth.py
-------
Everything about WHO the caller is and whether we trust them.

Two jobs:
  1. Passwords  -> hash them on the way in, verify them on login.
  2. JWT tokens -> issue one on successful login, and read the client_id
                   back out of it on every protected request.

GOLDEN RULE (from the senior's checklist):
  We ALWAYS take the client_id from the verified token — never from the
  request body. That is what stops one client reading another's leads.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import get_db
from models import Client

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# bcrypt is the hashing algorithm. CryptContext handles hash + verify for us.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tells FastAPI/Swagger that protected routes expect:
#   Authorization: Bearer <token>
# and that tokens are obtained from /auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Passwords ----------
def hash_password(plain_password: str) -> str:
    """Turn a plain password into a bcrypt hash (for storing)."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a login attempt against the stored hash."""
    return pwd_context.verify(plain_password, password_hash)


# ---------- JWT tokens ----------
def create_access_token(client_uuid: str) -> str:
    """
    Build a signed token that proves who the caller is. We put the client's
    PUBLIC uuid in 'sub' (subject) — never the internal integer pk — so the
    token itself doesn't leak the primary key. 'exp' makes it expire.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": client_uuid, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_client(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> int:
    """
    FastAPI dependency for protected routes. Decodes the token to get the
    client's uuid, looks the client up, and returns their INTERNAL integer id
    for use in queries. Raises 401 if the token or client is invalid.

    (Routes keep using the integer id internally; the uuid stays the only
    thing that travels over the wire.)
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_uuid = payload.get("sub")
        if client_uuid is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    client = db.query(Client).filter(Client.uuid == client_uuid).first()
    if client is None:
        raise credentials_error
    return client.id
