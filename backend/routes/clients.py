"""
routes/clients.py
-----------------
Create client accounts. For now this is a simple, manually-called endpoint
(via Postman) — there is no admin UI yet, which is fine per the spec.

POST /clients/create
    Body:    { "name": "...", "email": "...", "password": "..." }
    Returns: { "id": 1, "name": "...", "email": "..." }   (never the password)

The password is hashed before it ever touches the database.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Client
from schemas import ClientCreate, ClientOut
from auth import hash_password

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/create", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    # Reject duplicate emails up front with a clear message.
    existing = db.query(Client).filter(Client.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A client with this email already exists",
        )

    client = Client(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),   # never store plain text
    )
    db.add(client)
    db.commit()
    db.refresh(client)   # reload so we get the new id
    return client
