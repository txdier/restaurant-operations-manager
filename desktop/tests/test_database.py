import json
import sqlite3
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.migrations import DATA_SCHEMA_VERSION, default_state, migrate_state
from restaurant_manager.money import cents_to_yuan, yuan_to_cents
from restaurant_manager.storage_v6 import state_to_v6, validate_v6
from restaurant_manager.version import DATA_SCHEMA_MIN_APP_VERSION


def test_database_initializes_and_round_trips(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    assert state["schemaVersion"] == DATA_SCHEMA_VERSION
    state["settings"]["storeName"] = "测试餐馆"
    db.save(state, "test")
    assert db.load()["settings"]["storeName"] == "测试餐馆"
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_state'").fetchone()[0] == 0


def test_old_state_is_migrated_through_candidate_and_keeps_backup(tmp_path: Path):
    path = tmp_path / "old.db"
    old_state = {
        "schemaVersion": 1,
        "income": {"date": "2026-01-01", "hall": 10.01, "room": 2.02, "chess": 0.03, "delivery": 0.04},
        "expenses": [{"id": 7, "date": "2026-01-01", "mode": "快速记账", "category": "其他", "item": "测试", "amount": 12.34, "handler": "甲", "status": "有效"}],
    }
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
        conn.execute("INSERT INTO app_state VALUES(1,?,CURRENT_TIMESTAMP)", (json.dumps(old_state),))

    db = Database(path)
    state = db.load()
    assert state["schemaVersion"] == DATA_SCHEMA_VERSION
    assert state["incomeRecords"][0]["hall"] == 10.01
    assert state["incomeRecords"][0]["dineIn"] == 12.03
    assert state["incomeRecords"][0]["entryMode"] == "day"
    assert state["incomeRecords"][0]["periodStart"] == "2026-01-01"
    assert state["incomeRecords"][0]["periodEnd"] == "2026-01-01"
    assert state["expenseCategories"]
    assert state["importBatches"] == []
    assert list((tmp_path / "backups" / "migration").glob("*_before_schema_v1_to_v7.db"))
    assert not (tmp_path / ".migration-candidate.db").exists()

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "7"
        assert conn.execute("SELECT value FROM meta WHERE key='min_app_version'").fetchone()[0] == DATA_SCHEMA_MIN_APP_VERSION
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=6").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=7").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_state'").fetchone()[0] == 0
        assert conn.execute("PRAGMA freelist_count").fetchone()[0] == 0
        assert conn.execute("SELECT amount_cents FROM expenses_v6 WHERE id=7").fetchone()[0] == 1234
        income = conn.execute("SELECT dine_in_cents,chess_cents,delivery_cents FROM income_records_v6 WHERE id=1").fetchone()
        assert income == (1203, 3, 4)


def test_schema_v6_is_backed_up_then_compacted_to_v7_without_data_loss(tmp_path: Path):
    path = tmp_path / "restaurant.db"
    state = default_state()
    state["schemaVersion"] = 6
    state["expenses"] = [{"id": 8, "date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "迁移保留", "amount": 88.88, "handler": "甲", "status": "有效"}]
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
        conn.execute("INSERT INTO app_state VALUES(1,?,CURRENT_TIMESTAMP)", (json.dumps(state, ensure_ascii=False),))
        state_to_v6(conn, state)
        checks = validate_v6(conn, state)
        conn.execute("INSERT INTO schema_migrations(version,applied_at,detail) VALUES(6,CURRENT_TIMESTAMP,?)", (json.dumps(checks),))
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta VALUES('schema_version','6')")
        conn.commit()

    db = Database(path)

    assert db.load()["expenses"][0]["item"] == "迁移保留"
    assert list((tmp_path / "backups" / "migration").glob("*_before_schema_v6_to_v7.db"))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "7"
        assert conn.execute("SELECT amount_cents FROM expenses_v6 WHERE id=8").fetchone()[0] == 8888
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=7").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_state'").fetchone()[0] == 0


def test_money_conversion_uses_decimal_rounding():
    assert yuan_to_cents("12.34") == 1234
    assert yuan_to_cents("0.005") == 1
    assert yuan_to_cents(680) == 68000
    assert cents_to_yuan(1234) == "12.34"


def test_legacy_core_save_syncs_relational_snapshot(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenses"].append({"id": 10, "date": "2026-08-27", "mode": "快速记账", "category": "耗材", "item": "抹布", "amount": 9.8, "handler": "甲", "status": "有效"})
    db.save(state)
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT amount_cents FROM expenses_v6 WHERE id=10").fetchone()[0] == 980
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_state'").fetchone()[0] == 0


def test_backup_restore_preserves_safety_copy(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["settings"]["storeName"] = "备份版本"
    db.save(state)
    backup = db.backup(tmp_path / "backups")
    state["settings"]["storeName"] = "当前版本"
    db.save(state)
    db.restore(backup)
    assert db.load()["settings"]["storeName"] == "备份版本"
    assert list((tmp_path / "backups").glob("*_before_restore.db"))


def test_restore_removes_stale_wal_sidecars(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["settings"]["storeName"] = "正确备份"
    db.save(state)
    backup = db.backup(tmp_path / "backups")

    wal = Path(str(db.path) + "-wal")
    shm = Path(str(db.path) + "-shm")
    wal.write_bytes(b"stale-wal")
    shm.write_bytes(b"stale-shm")

    db.restore(backup)
    assert db.load()["settings"]["storeName"] == "正确备份"
    assert not wal.exists()
    assert not shm.exists()


def test_frontend_save_cannot_clear_password_hash(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["settings"]["passwordHash"] = "protected-value"
    db.save(state)
    visible = db.load()
    del visible["settings"]["passwordHash"]
    db.save(visible)
    assert db.load()["settings"]["passwordHash"] == "protected-value"


def test_existing_state_gets_default_auto_lock_timeout():
    state = migrate_state({"schemaVersion": 4, "settings": {"storeName": "旧门店"}})

    assert state["settings"]["storeName"] == "旧门店"
    assert state["settings"]["autoLockMinutes"] == 15
    assert state["settings"]["appName"] == "餐馆经营管理系统"
    assert state["settings"]["desktopShortcutName"] == "餐馆经营管理系统"
    assert state["settings"]["autoCheckUpdates"] is True
