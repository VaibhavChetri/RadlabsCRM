"""
The one-time migration from the old client-inbox schema to the CRM schema.
Runs against its own throwaway database, because it drops tables.
"""

import openpyxl
import pytest
from sqlalchemy import create_engine, inspect, text

from conftest import database_url, drop_database, recreate_database

DB_NAME = "leadsdb_migration_test"

OLD_SCHEMA = [
    """CREATE TABLE clients (
        id INT AUTO_INCREMENT PRIMARY KEY,
        uuid CHAR(36) NOT NULL UNIQUE DEFAULT (UUID()),
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE leads (
        id INT AUTO_INCREMENT PRIMARY KEY,
        client_id INT NOT NULL,
        name VARCHAR(255), email VARCHAR(255), phone VARCHAR(50), message TEXT,
        status ENUM('new','contacted','closed') NOT NULL DEFAULT 'new',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients(id))""",
]


@pytest.fixture
def old_engine():
    from auth import hash_password

    recreate_database(DB_NAME)
    engine = create_engine(database_url(DB_NAME))
    with engine.begin() as conn:
        for ddl in OLD_SCHEMA:
            conn.execute(text(ddl))
        conn.execute(
            text("INSERT INTO clients (name, email, password_hash) VALUES "
                 "('Test Client', 'Radlabs@leads.com', :admin_hash), "
                 "('Acme Realty', 'acme@example.com', 'x')"),
            {"admin_hash": hash_password("Radlabs123")},
        )
        conn.execute(text(
            "INSERT INTO leads (client_id, name, email, phone, message, status) VALUES "
            "(1, 'Ravi', 'ravi@acme.com', '98765', 'Hi', 'new'), "
            "(2, 'Meera', 'meera@x.com', NULL, NULL, 'closed')"))
    yield engine
    engine.dispose()
    drop_database(DB_NAME)


def test_migration_backs_up_old_data_then_builds_empty_crm(old_engine, tmp_path):
    import migrate_phase1
    from auth import verify_password

    backup = tmp_path / "backup.xlsx"

    migrate_phase1.run(old_engine, backup)

    # 1. Backup holds every old lead and client (but no password hashes).
    wb = openpyxl.load_workbook(backup)
    lead_rows = list(wb["Leads"].values)
    client_rows = list(wb["Clients"].values)
    assert len(lead_rows) == 1 + 2
    assert ("Ravi" in lead_rows[1]) and ("Test Client" in lead_rows[1])
    assert len(client_rows) == 1 + 2
    assert not any("password" in str(h).lower() for h in client_rows[0])

    # 2. Old tables gone, new tables there.
    tables = set(inspect(old_engine).get_table_names())
    assert "clients" not in tables
    assert {"users", "statuses", "leads", "calls", "status_changes",
            "import_presets", "imports"} <= tables
    lead_columns = {c["name"] for c in inspect(old_engine).get_columns("leads")}
    assert "client_id" not in lead_columns and "linkedin_url" in lead_columns

    with old_engine.connect() as conn:
        statuses = conn.execute(
            text("SELECT name, is_exit FROM statuses ORDER BY sort_order")).all()
        users = conn.execute(
            text("SELECT email, role, is_active, password_hash FROM users")).all()
        lead_count = conn.execute(text("SELECT COUNT(*) FROM leads")).scalar()

    # 3. 10 statuses in pipeline order; the last 4 are exit stages.
    assert [s.name for s in statuses] == [
        "New", "Attempted", "Connected", "Interested", "Meeting booked",
        "Proposal sent", "Won", "Lost", "Not interested", "Do not call"]
    assert [bool(s.is_exit) for s in statuses] == [False] * 6 + [True] * 4

    # 4. Exactly one user: the admin, with the same password as before.
    assert len(users) == 1
    admin = users[0]
    assert (admin.email, admin.role, bool(admin.is_active)) == ("Radlabs@leads.com", "admin", True)
    assert verify_password("Radlabs123", admin.password_hash)

    # 5. CRM starts empty.
    assert lead_count == 0


def test_migration_refuses_to_run_twice(old_engine, tmp_path):
    import migrate_phase1

    migrate_phase1.run(old_engine, tmp_path / "first.xlsx")

    with pytest.raises(migrate_phase1.MigrationError):
        migrate_phase1.run(old_engine, tmp_path / "second.xlsx")
    assert not (tmp_path / "second.xlsx").exists()
