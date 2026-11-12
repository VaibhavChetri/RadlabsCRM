"""
routes/leads.py
---------------
All lead-related endpoints live here. We build them across the next steps,
in the order the senior's prompt lists them:

  Step 3 -> POST  /leads/submit            (public: website form posts here)
  Step 4 -> GET   /leads/                   (protected: this client's leads)
  Step 5 -> GET   /leads/export             (protected: Excel download)
  Step 6 -> PATCH /leads/{lead_id}/status   (protected: change status)

For now this is an empty router so the app structure is complete. Endpoints
get added one at a time so each can be tested on its own.
"""

import io
from typing import List
from datetime import date, timedelta
from collections import Counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import openpyxl

from database import get_db
from models import Client, Lead
from schemas import LeadSubmit, LeadOut, LeadStatusUpdate
from auth import get_current_client
from notifications import notify_new_lead

router = APIRouter(prefix="/leads", tags=["leads"])


# ---------- Step 3: PUBLIC lead submission ----------
@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_lead(
    payload: LeadSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    PUBLIC endpoint — no login required. A client's website contact form
    POSTs here. The form tells us which client the lead belongs to via
    `client_id`.

    We check that client_id points at a real client (so we return a clean
    error instead of a database crash if it doesn't), then save the lead.
    """
    # Look the client up by their PUBLIC uuid (what the website form sends).
    client = db.query(Client).filter(Client.uuid == payload.client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No client found with id {payload.client_id}",
        )

    # Store the lead against the client's INTERNAL integer id (the FK).
    lead = Lead(
        client_id=client.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
        # status defaults to 'new' (set in the database/model)
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Email the client about the new lead — IN THE BACKGROUND, so the form
    # gets its instant reply. notify_new_lead() is safe: if the email fails,
    # it just logs the problem and the lead (already saved) is unaffected.
    background_tasks.add_task(
        notify_new_lead, client.email, lead.name, lead.message
    )

    return {"message": "Lead received", "lead_id": lead.id}


# ---------- Step 4: PROTECTED — list the logged-in client's leads ----------
@router.get("/", response_model=List[LeadOut])
def list_my_leads(
    client_id: int = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    PROTECTED endpoint — needs a valid 'Authorization: Bearer <token>' header.

    SECURITY (the most important rule in this project):
      `client_id` comes from get_current_client(), which reads it out of the
      verified JWT token. We NEVER take it from the request. That is what makes
      it impossible for one client to see another client's leads.

    Returns the client's leads, newest first.
    """
    leads = (
        db.query(Lead)
        .filter(Lead.client_id == client_id)
        .order_by(Lead.submitted_at.desc())
        .all()
    )
    return leads


# ---------- Step 5: PROTECTED — download leads as an Excel file ----------
@router.get("/export")
def export_my_leads(
    client_id: int = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    PROTECTED endpoint. Builds an Excel (.xlsx) file of THIS client's leads
    and sends it back as a file download.

    Same security rule: we only ever export leads for the client_id taken
    from the token.
    """
    leads = (
        db.query(Lead)
        .filter(Lead.client_id == client_id)
        .order_by(Lead.submitted_at.desc())
        .all()
    )

    # Build the spreadsheet in memory.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"

    # Header row.
    ws.append(["Name", "Email", "Phone", "Message", "Status", "Submitted At"])

    # One row per lead.
    for lead in leads:
        ws.append([
            lead.name,
            lead.email,
            lead.phone,
            lead.message,
            lead.status,
            str(lead.submitted_at),
        ])

    # Save the workbook into a memory buffer (no temp file on disk).
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    # The Content-Disposition header tells the browser/Postman to DOWNLOAD
    # the file and what to name it.
    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": "attachment; filename=leads.xlsx"},
    )


# ---------- Step 6: PROTECTED — change a lead's status ----------
@router.patch("/{lead_id}/status", response_model=LeadOut)
def update_lead_status(
    lead_id: int,
    payload: LeadStatusUpdate,
    client_id: int = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    PROTECTED endpoint. Move a lead through new -> contacted -> closed.

    SECURITY: we look up the lead by BOTH its id AND the token's client_id.
    So if the lead belongs to someone else, the query finds nothing and we
    return 404 — a client can never edit another client's lead.
    """
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.client_id == client_id)
        .first()
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    lead.status = payload.status
    db.commit()
    db.refresh(lead)
    return lead


# ---------- Analytics: PROTECTED — lead stats for the dashboard ----------
@router.get("/stats")
def lead_stats(
    client_id: int = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    PROTECTED. Aggregate numbers for THIS client's dashboard: totals, status
    breakdown, conversion rate, recent counts, and a 14-day trend.

    These are the only Google-Analytics-style metrics that actually map to a
    lead inbox (counts, conversions, funnel, trend-over-time). Same token
    security as the other endpoints — a client only ever sees their own stats.
    """
    # ponytail: one query + compute in Python. Fine for normal lead volumes;
    # switch to SQL GROUP BY only if a client ever has ~100k+ leads.
    rows = (
        db.query(Lead.status, Lead.submitted_at)
        .filter(Lead.client_id == client_id)
        .all()
    )

    total = len(rows)
    status_counts = Counter(s for s, _ in rows)
    by_status = {k: status_counts.get(k, 0) for k in ("new", "contacted", "closed")}
    conversion_rate = round(by_status["closed"] / total * 100, 1) if total else 0.0

    today = date.today()
    today_count = sum(1 for _, ts in rows if ts and ts.date() == today)
    last_7_days = sum(1 for _, ts in rows if ts and ts.date() > today - timedelta(days=7))

    # 14-day trend, oldest -> newest, zero-filled so the chart has every day.
    per_day = Counter(ts.date() for _, ts in rows if ts)
    trend = [
        {"date": (today - timedelta(days=i)).isoformat(),
         "count": per_day.get(today - timedelta(days=i), 0)}
        for i in range(13, -1, -1)
    ]

    return {
        "total": total,
        "by_status": by_status,
        "conversion_rate": conversion_rate,
        "today": today_count,
        "last_7_days": last_7_days,
        "trend": trend,
    }
