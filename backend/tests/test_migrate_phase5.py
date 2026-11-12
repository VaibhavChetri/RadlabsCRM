"""Phase 5 migration: the built-in Apollo preset is put in the live database."""

from models import ImportPreset


def test_migration_seeds_the_builtin_presets_once(db):
    import migrate_phase5
    from database import engine

    db.query(ImportPreset).delete()
    db.commit()

    assert migrate_phase5.run(engine) == {"builtin_presets": ["Apollo"]}
    migrate_phase5.run(engine)  # safe to run again

    db.expire_all()
    presets = db.query(ImportPreset).all()
    assert [(p.name, p.is_builtin) for p in presets] == [("Apollo", True)]
    assert presets[0].mapping["Person Linkedin Url"] == "linkedin_url"
