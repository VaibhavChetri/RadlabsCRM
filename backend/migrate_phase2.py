"""
migrate_phase2.py
-----------------
ONE-TIME change: the single Notes box on a lead becomes a notes thread.

Steps (safe to run again; a second run does nothing):
  1. Create the `lead_notes` table.
  2. Copy each lead's old Notes text into the thread as its first entry,
     signed by whoever last edited it (or, if unknown, who added the lead).
  3. Drop the old leads.notes, notes_updated_by, notes_updated_at columns.

Run from backend/ with the venv active:
    python migrate_phase2.py
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from models import LeadNote

OLD_COLUMNS = ("notes", "notes_updated_by", "notes_updated_at")


def run(engine: Engine) -> dict:
    LeadNote.__table__.create(engine, checkfirst=True)

    columns = {c["name"] for c in inspect(engine).get_columns("leads")}
    if "notes" not in columns:
        return {"notes_moved": 0}

    with engine.begin() as conn:
        moved = conn.execute(text(
            "INSERT INTO lead_notes (lead_id, user_id, body, created_at) "
            "SELECT id, COALESCE(notes_updated_by, created_by), notes, "
            "       COALESCE(notes_updated_at, created_at) "
            "FROM leads WHERE notes IS NOT NULL AND TRIM(notes) <> '' "
            "  AND COALESCE(notes_updated_by, created_by) IS NOT NULL"
        )).rowcount

    # The foreign key must go before its column can be dropped.
    for fk in inspect(engine).get_foreign_keys("leads"):
        if fk["constrained_columns"] == ["notes_updated_by"]:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE leads DROP FOREIGN KEY `{fk['name']}`"))
    drops = ", ".join(f"DROP COLUMN `{c}`" for c in OLD_COLUMNS if c in columns)
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE leads {drops}"))

    return {"notes_moved": moved}


if __name__ == "__main__":
    from database import engine

    summary = run(engine)
    print(f"Notes thread ready. {summary['notes_moved']} old note(s) moved into it.")
