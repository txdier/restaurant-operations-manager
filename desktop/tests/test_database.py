import json
import sqlite3
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.migrations import DATA_SCHEMA_VERSION


def test_database_initializes_and_round_trips(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    assert state["schemaVersion"] == DATA_SCHEMA_VERSION
    state["settings"]["storeName"] = "测试餐馆"
    db.save(state, "test")
    assert db.load()["settings"]["storeName"] == "测试餐馆"


def test_old_state_is_migrated(tmp_path: Path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
        conn.execute("INSERT INTO app_state VALUES(1,?,CURRENT_TIMESTAMP)", (json.dumps({"schemaVersion": 1, "income": {"date": "2026-01-01", "hall": 10}}),))
    state = Database(path).load()
    assert state["schemaVersion"] == DATA_SCHEMA_VERSION
    assert state["incomeRecords"][0]["hall"] == 10


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


def test_frontend_save_cannot_clear_password_hash(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["settings"]["passwordHash"] = "protected-value"
    db.save(state)
    visible = db.load()
    del visible["settings"]["passwordHash"]
    db.save(visible)
    assert db.load()["settings"]["passwordHash"] == "protected-value"
