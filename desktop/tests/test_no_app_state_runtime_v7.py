from pathlib import Path


def test_business_modules_do_not_read_or_write_app_state():
    root = Path(__file__).resolve().parents[1] / "restaurant_manager"
    migration_only = {"database.py", "migrations.py", "storage_diagnostics_v6.py"}
    offenders = []
    for source in root.glob("*.py"):
        if source.name in migration_only:
            continue
        text = source.read_text(encoding="utf-8").lower()
        if "app_state" in text:
            offenders.append(source.name)
    assert offenders == []


def test_app_state_is_never_written_after_legacy_import():
    root = Path(__file__).resolve().parents[1] / "restaurant_manager"
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in root.glob("*.py"))
    assert "update app_state" not in source
    assert "insert into app_state" not in source
