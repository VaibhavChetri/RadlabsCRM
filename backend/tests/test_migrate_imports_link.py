"""Migration: leads remember the import that added them (for "View new leads").
Runs against its own throwaway database, because it alters tables."""

import pytest
from sqlalchemy import create_engine, inspect, text

from conftest import database_url, drop_database, recreate_database

DB_NAME = "leadsdb_migration_imports_test"

# The two tables as they were before this change.
OLD_SCHEMA = [
    """CREATE TABLE imports (
        id INT AUTO_INCREMENT PRIMARY KEY, file_name VARCHAR(255) NOT NULL)""",
    """CREATE TABLE leads (
        id INT AUTO_INCREMENT PRIMARY KEY, first_name VARCHAR(100))""",
]


@pytest.fixture
def old_engine():
    recreate_database(DB_NAME)
    engine = create_engine(database_url(DB_NAME))
    with engine.begin() as conn:
        for ddl in OLD_SCHEMA:
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO imports (file_name) VALUES ('a.csv'), ('b.csv')"))
        conn.execute(text("INSERT INTO leads (first_name) VALUES ('Ravi')"))
    yield engine
    engine.dispose()
    drop_database(DB_NAME)


def test_imports_get_a_uuid_and_leads_get_an_import_link(old_engine):
    import migrate_import_link

    assert migrate_import_link.run(old_engine) == {"imports_given_uuid": 2}
    assert migrate_import_link.run(old_engine) == {"imports_given_uuid": 0}  # safe to run again

    with old_engine.connect() as conn:
        uuids = [r[0] for r in conn.execute(text("SELECT uuid FROM imports"))]
        lead = conn.execute(text("SELECT first_name, import_id FROM leads")).one()
    assert len(set(uuids)) == 2 and all(len(u) == 36 for u in uuids)
    assert tuple(lead) == ("Ravi", None)
    fks = inspect(old_engine).get_foreign_keys("leads")
    assert any(fk["constrained_columns"] == ["import_id"] and fk["referred_table"] == "imports"
               for fk in fks)
