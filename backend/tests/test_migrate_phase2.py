"""
Phase 2 migration: the single Notes box becomes a notes thread.
Runs against its own throwaway database, because it drops columns.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from conftest import database_url, drop_database, recreate_database

DB_NAME = "leadsdb_migration2_test"

# The Phase 1 tables this migration touches, as they were.
PHASE1_SCHEMA = [
    """CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL)""",
    """CREATE TABLE leads (
        id INT AUTO_INCREMENT PRIMARY KEY,
        first_name VARCHAR(100),
        created_by INT, created_at DATETIME NOT NULL,
        notes TEXT, notes_updated_by INT, notes_updated_at DATETIME,
        FOREIGN KEY (created_by) REFERENCES users(id),
        FOREIGN KEY (notes_updated_by) REFERENCES users(id))""",
]


@pytest.fixture
def phase1_engine():
    recreate_database(DB_NAME)
    engine = create_engine(database_url(DB_NAME))
    with engine.begin() as conn:
        for ddl in PHASE1_SCHEMA:
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Asha'), (2, 'Vikram')"))
        conn.execute(text(
            "INSERT INTO leads (id, first_name, created_by, created_at, notes, "
            "notes_updated_by, notes_updated_at) VALUES "
            "(1, 'Ravi', 1, '2026-11-10 09:00:00', 'Wants a demo', 2, '2026-11-11 10:30:00'),"
            "(2, 'Meera', 1, '2026-11-10 09:00:00', NULL, NULL, NULL),"
            "(3, 'Old', 1, '2026-11-10 09:00:00', 'Typed long ago', NULL, NULL)"))
    yield engine
    engine.dispose()
    drop_database(DB_NAME)


def test_old_notes_become_the_first_thread_entry_and_columns_go(phase1_engine):
    import migrate_phase2

    summary = migrate_phase2.run(phase1_engine)

    assert summary == {"notes_moved": 2}
    with phase1_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT lead_id, user_id, body, created_at FROM lead_notes ORDER BY lead_id")).all()
    assert [(r.lead_id, r.user_id, r.body, str(r.created_at)) for r in rows] == [
        (1, 2, "Wants a demo", "2026-11-11 10:30:00"),
        # No editor recorded: fall back to who added the lead and when.
        (3, 1, "Typed long ago", "2026-11-10 09:00:00"),
    ]
    columns = {c["name"] for c in inspect(phase1_engine).get_columns("leads")}
    assert not columns & {"notes", "notes_updated_by", "notes_updated_at"}


def test_running_it_twice_changes_nothing(phase1_engine):
    import migrate_phase2

    migrate_phase2.run(phase1_engine)

    assert migrate_phase2.run(phase1_engine) == {"notes_moved": 0}
    with phase1_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM lead_notes")).scalar() == 2
