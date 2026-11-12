"""
migrate_phase5.py
-----------------
ONE-TIME step for the Import feature: put the built-in column presets
(Apollo) in the database. The import tables already exist (Phase 1).

Safe to run again: it refreshes the built-in presets and touches nothing else.

Run from backend/ with the venv active:
    python migrate_phase5.py
"""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import import_engine


def run(engine: Engine) -> dict:
    with Session(engine) as db:
        import_engine.seed_builtin_presets(db)
        db.commit()
    return {"builtin_presets": list(import_engine.BUILTIN_PRESETS)}


if __name__ == "__main__":
    from database import engine

    print(run(engine))
