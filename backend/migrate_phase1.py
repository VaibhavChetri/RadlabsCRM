"""
migrate_phase1.py
-----------------
ONE-TIME move from the old client-inbox schema to the Radlabs CRM schema.

Steps (stops before dropping anything if a step fails):
  1. Check the old tables exist and the admin login (Radlabs@leads.com) is there.
  2. Export the old leads and client list to an Excel backup.
  3. Drop the old `leads` and `clients` tables.
  4. Create the new tables, seed the 10 pipeline statuses.
  5. Create the admin user with the SAME password hash (same password as now).

Run from backend/ with the venv active:
    python migrate_phase1.py
The backup lands in ../backups/ (git-ignored: it holds personal data).
"""

import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database import Base
from models import User, seed_statuses

ADMIN_EMAIL = "Radlabs@leads.com"
ADMIN_NAME = "Radlabs Admin"

LEAD_COLUMNS = ["id", "client", "name", "email", "phone", "message", "status", "submitted_at"]
CLIENT_COLUMNS = ["id", "uuid", "name", "email", "created_at"]  # never the password hash


class MigrationError(RuntimeError):
    pass


def export_old_data(engine: Engine, path: Path) -> tuple[int, int]:
    """Write old leads and clients to an .xlsx file. Returns (leads, clients) counts."""
    with engine.connect() as conn:
        leads = conn.execute(text(
            "SELECT l.id, c.name, l.name, l.email, l.phone, l.message, l.status, "
            "l.submitted_at FROM leads l LEFT JOIN clients c ON c.id = l.client_id "
            "ORDER BY l.id")).all()
        clients = conn.execute(text(
            "SELECT id, uuid, name, email, created_at FROM clients ORDER BY id")).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(LEAD_COLUMNS)
    for row in leads:
        ws.append(list(row))
    ws = wb.create_sheet("Clients")
    ws.append(CLIENT_COLUMNS)
    for row in clients:
        ws.append(list(row))

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return len(leads), len(clients)


def run(engine: Engine, backup_path: Path) -> dict:
    tables = set(inspect(engine).get_table_names())
    if "clients" not in tables or "leads" not in tables:
        raise MigrationError("Old tables not found. Has the migration already run?")

    with engine.connect() as conn:
        admin = conn.execute(
            text("SELECT name, password_hash FROM clients WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        ).first()
    if admin is None:
        raise MigrationError(f"Admin login {ADMIN_EMAIL} not found in old clients table.")

    lead_count, client_count = export_old_data(engine, backup_path)
    check = openpyxl.load_workbook(backup_path, read_only=True)
    written = (check["Leads"].max_row - 1, check["Clients"].max_row - 1)
    check.close()
    if written != (lead_count, client_count):
        raise MigrationError("Backup file does not match the database. Nothing was dropped.")

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE leads"))
        conn.execute(text("DROP TABLE clients"))

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_statuses(db)
        db.add(User(name=ADMIN_NAME, email=ADMIN_EMAIL,
                    password_hash=admin.password_hash, role="admin", is_active=True))
        db.commit()

    return {"backup": str(backup_path), "old_leads": lead_count, "old_clients": client_count}


if __name__ == "__main__":
    from database import engine

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = Path(__file__).resolve().parent.parent
    target = root / "backups" / f"pre-crm-backup-{stamp}.xlsx"
    try:
        summary = run(engine, target)
    except MigrationError as exc:
        print(f"Migration stopped: {exc}")
        sys.exit(1)
    print(f"Backup written: {summary['backup']}")
    print(f"  {summary['old_leads']} old leads, {summary['old_clients']} old clients")
    print("New CRM tables created. Admin login:", ADMIN_EMAIL)
