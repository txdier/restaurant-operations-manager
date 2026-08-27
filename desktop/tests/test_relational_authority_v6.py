import sqlite3
from pathlib import Path

from restaurant_manager.database import Database


def test_load_works_without_app_state_and_uses_relational_tables(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenses"] = [{"id": 1, "date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "真实数据", "amount": 12.34, "handler": "甲", "status": "有效"}]
    db.save(state, "seed")

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='app_state'").fetchone()[0] == 0

    loaded = db.load()
    assert loaded["expenses"][0]["item"] == "真实数据"


def test_direct_relational_change_is_visible_through_legacy_load(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenses"] = [{"id": 2, "date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "原项目", "amount": 10, "handler": "甲", "status": "有效"}]
    db.save(state, "seed")

    with sqlite3.connect(db.path) as conn:
        conn.execute("UPDATE expenses_v6 SET item=?, amount_cents=? WHERE id=2", ("关系表项目", 2001))
        conn.commit()

    loaded = db.load()
    assert loaded["expenses"][0]["item"] == "关系表项目"
    assert loaded["expenses"][0]["amount"] == 20.01
