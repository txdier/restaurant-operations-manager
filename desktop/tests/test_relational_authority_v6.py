import json
import sqlite3
from pathlib import Path

from restaurant_manager.database import Database


def test_load_rebuilds_known_groups_from_relational_tables(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenses"] = [{"id": 1, "date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "真实数据", "amount": 12.34, "handler": "甲", "status": "有效"}]
    db.save(state, "seed")

    with sqlite3.connect(db.path) as conn:
        payload = json.loads(conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()[0])
        payload["expenses"][0]["item"] = "被篡改的旧镜像"
        payload["futureUnknownData"] = {"keep": True}
        conn.execute("UPDATE app_state SET payload=? WHERE id=1", (json.dumps(payload, ensure_ascii=False),))
        conn.commit()

    loaded = db.load()
    assert loaded["expenses"][0]["item"] == "真实数据"
    assert loaded["futureUnknownData"] == {"keep": True}


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
