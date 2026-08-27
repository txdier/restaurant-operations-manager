import sqlite3
from pathlib import Path

from restaurant_manager.database import Database


def test_legacy_save_incrementally_updates_core_relational_tables(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [{"id": 1, "name": "耗材", "active": True}]
    state["products"] = [{"id": 10, "name": "抽纸", "category": "耗材", "brand": "", "spec": "", "unit": "包", "stocktake": True, "reminder": False, "active": True}]
    state["expenses"] = [{"id": 20, "date": "2026-08-27", "mode": "详细采购", "category": "耗材", "item": "抽纸 2包", "amount": 12.34, "handler": "甲", "status": "有效", "productId": 10, "qty": 2, "unit": "包", "price": 6.17}]
    state["incomeRecords"] = [{"id": 30, "date": "2026-08-27", "entryMode": "day", "periodStart": "2026-08-27", "periodEnd": "2026-08-27", "dineIn": 100.01, "chess": 2.02, "delivery": 3.03, "note": ""}]
    db.save(state, "legacy_core_save")

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT name,unit FROM products_v6 WHERE id=10").fetchone() == ("抽纸", "包")
        assert conn.execute("SELECT amount_cents,unit_price_cents,product_id FROM expenses_v6 WHERE id=20").fetchone() == (1234, 617, 10)
        assert conn.execute("SELECT dine_in_cents,chess_cents,delivery_cents FROM income_records_v6 WHERE id=30").fetchone() == (10001, 202, 303)
        assert conn.execute("SELECT value FROM meta WHERE key='relational_snapshot_dirty'").fetchone()[0] == "0"

    state = db.load()
    state["products"][0]["name"] = "抽纸新名"
    state["expenses"][0]["amount"] = 20.01
    db.save(state, "legacy_core_update")
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT name FROM products_v6 WHERE id=10").fetchone()[0] == "抽纸新名"
        assert conn.execute("SELECT amount_cents FROM expenses_v6 WHERE id=20").fetchone()[0] == 2001

    state = db.load()
    state["expenses"] = []
    db.save(state, "legacy_core_delete")
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM expenses_v6 WHERE id=20").fetchone()[0] == 0


def test_unsupported_legacy_group_marks_relational_snapshot_dirty(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["stocktakes"] = [{"id": 1, "date": "2026-08-27", "kind": "临时盘点", "rows": []}]
    db.save(state, "legacy_stocktake")
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT value FROM meta WHERE key='relational_snapshot_dirty'").fetchone()[0] == "1"
