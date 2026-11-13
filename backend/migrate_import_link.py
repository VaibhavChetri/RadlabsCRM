"""
migrate_import_link.py
----------------------
ONE-TIME change: each lead remembers the import that added it, so the import
results can open exactly those leads (GET /leads?import=<import uuid>).

Steps (safe to run again; a second run changes nothing):
  1. imports.uuid: a public id for every import (past imports get one too).
  2. leads.import_id: which import added the lead (NULL for leads added by hand
     and for leads imported before this change).

Run from backend/ with the venv active:
    python migrate_import_link.py
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _columns(engine: Engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def run(engine: Engine) -> dict:
    given = 0
    if "uuid" not in _columns(engine, "imports"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE imports ADD COLUMN uuid VARCHAR(36) NULL"))
            given = conn.execute(text("UPDATE imports SET uuid = UUID() WHERE uuid IS NULL")).rowcount
            conn.execute(text("ALTER TABLE imports MODIFY uuid VARCHAR(36) NOT NULL, "
                              "ADD UNIQUE INDEX ix_imports_uuid (uuid)"))

    if "import_id" not in _columns(engine, "leads"):
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE leads ADD COLUMN import_id INT NULL, "
                "ADD INDEX ix_leads_import_id (import_id), "
                "ADD CONSTRAINT fk_leads_import_id FOREIGN KEY (import_id) "
                "REFERENCES imports(id) ON DELETE SET NULL"))

    return {"imports_given_uuid": given}


if __name__ == "__main__":
    from database import engine

    summary = run(engine)
    print(f"Leads can now be traced to their import. "
          f"{summary['imports_given_uuid']} past import(s) given an id.")
