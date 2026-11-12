"""
lead_export.py
--------------
Turns a list of leads into an .xlsx file (the All-leads "Export to Excel").
Times are written in the user's local time, so the file matches the screen.
"""

from datetime import date, datetime, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from models import Lead, LeadNote

PRIORITY_LABELS = {"hot": "Hot", "warm": "Warm", "cold": "Cold"}
EXCEL_CELL_LIMIT = 32_767  # characters

# (header, how to read the value from a lead)
COLUMNS = [
    ("First name", lambda lead: lead.first_name),
    ("Last name", lambda lead: lead.last_name),
    ("Job title", lambda lead: lead.job_title),
    ("Email", lambda lead: lead.email),
    ("Phone", lambda lead: lead.phone),
    ("Phone 2", lambda lead: lead.phone_2),
    ("LinkedIn URL", lambda lead: lead.linkedin_url),
    ("Company", lambda lead: lead.company),
    ("Website", lambda lead: lead.website),
    ("Industry", lambda lead: lead.industry),
    ("Company size", lambda lead: lead.company_size),
    ("City", lambda lead: lead.city),
    ("Country", lambda lead: lead.country),
    ("Source", lambda lead: lead.source),
    ("Priority", lambda lead: PRIORITY_LABELS[lead.priority]),
    ("Status", lambda lead: lead.status.name),
    ("Owner", lambda lead: lead.owner.name if lead.owner else "Unassigned"),
    ("Calls", lambda lead: lead.call_attempts),
    ("Last called", lambda lead: lead.last_called_at),
    ("Next follow-up", lambda lead: lead.next_follow_up),
    ("Added to CRM", lambda lead: lead.created_at),
    ("Added by", lambda lead: lead.creator.name if lead.creator else None),
    ("Last updated", lambda lead: lead.updated_at),
]
DATETIME_FORMAT = "dd mmm yyyy hh:mm"
DATE_FORMAT = "dd mmm yyyy"


def _notes_text(notes: list[LeadNote], to_local) -> str:
    """The whole thread in one cell, newest first: '12 Nov 2026 10:00 · Asha: text'."""
    lines = [f"{to_local(n.created_at):%d %b %Y %H:%M} · {n.author.name}: {n.body}" for n in notes]
    text = "\n".join(lines)
    if len(text) > EXCEL_CELL_LIMIT:
        text = text[:EXCEL_CELL_LIMIT - 1] + "…"
    return text


def leads_workbook(leads: list[Lead], notes_by_lead: dict[int, list[LeadNote]],
                   tz_offset: int = 0) -> bytes:
    """`tz_offset` is the user's local time minus UTC, in minutes (IST = 330)."""
    def to_local(utc: datetime) -> datetime:
        return utc + timedelta(minutes=tz_offset)

    book = Workbook(write_only=True)
    sheet = book.create_sheet("Leads")
    header = []
    for title in [name for name, _ in COLUMNS] + ["Notes"]:
        cell = WriteOnlyCell(sheet, value=title)
        cell.font = Font(bold=True)
        header.append(cell)
    sheet.append(header)

    for lead in leads:
        row = []
        for _, read in COLUMNS:
            value = read(lead)
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, datetime):
                cell.value = to_local(value)
                cell.number_format = DATETIME_FORMAT
            elif isinstance(value, date):
                cell.number_format = DATE_FORMAT
            row.append(cell)
        row.append(_notes_text(notes_by_lead.get(lead.id, []), to_local))
        sheet.append(row)

    out = BytesIO()
    book.save(out)
    return out.getvalue()
