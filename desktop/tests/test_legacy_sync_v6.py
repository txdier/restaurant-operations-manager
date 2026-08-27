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


def test_legacy_save_syncs_extended_relational_groups(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["salesRecords"] = [{"id": 40, "date": "2026-08-27", "rows": [{"categoryId": 1, "category": "主食", "qty": 2, "amount": 20.01}]}]
    state["stocktakes"] = [{"id": 50, "date": "2026-08-27", "kind": "临时盘点", "rows": [{"productId": None, "product": "抽纸", "unit": "包", "previous": 3, "actual": 2, "change": -1, "note": ""}]}]
    state["employees"] = [{"id": 60, "name": "张三", "role": "厨师", "salary": 6000.01, "startDate": "2026-01-01", "active": True}]
    state["payrolls"] = [{"month": "2026-08", "confirmed": True, "rows": [{"employeeId": 60, "name": "张三", "role": "厨师", "standard": 6000.01, "amount": 5800.02, "note": "请假"}]}]
    state["suppliers"] = [{"id": 70, "name": "供应商A", "contact": "李四", "phone": "123", "qualification": "有效", "note": "", "active": True}]
    state["reminders"] = [{"id": 80, "name": "补纸", "product": "抽纸", "date": "2026-09-01", "cycle": 7, "done": False}]
    state["assets"] = [{"id": 90, "name": "冰箱", "qty": 1, "unit": "台", "date": "2026-08-01", "amount": 2500.55, "status": "使用中", "note": "", "type": "asset"}]
    state["importBatches"] = [{"id": "batch-a", "file": "a.xlsx", "importedAt": "2026-08-27T12:00:00", "quickExpenses": 1}]
    db.save(state, "legacy_extended_save")

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT amount_cents FROM sales_lines_v6 WHERE sales_record_id=40").fetchone()[0] == 2001
        assert conn.execute("SELECT actual_quantity FROM stocktake_lines_v6 WHERE stocktake_id=50").fetchone()[0] == 2
        assert conn.execute("SELECT standard_salary_cents FROM employees_v6 WHERE id=60").fetchone()[0] == 600001
        assert conn.execute("SELECT actual_salary_cents FROM payroll_lines_v6").fetchone()[0] == 580002
        assert conn.execute("SELECT name FROM suppliers_v6 WHERE id=70").fetchone()[0] == "供应商A"
        assert conn.execute("SELECT cycle_days FROM reminders_v6 WHERE id=80").fetchone()[0] == 7
        assert conn.execute("SELECT amount_cents FROM assets_v6 WHERE id=90").fetchone()[0] == 250055
        assert conn.execute("SELECT file_name FROM import_batches_v6 WHERE id='batch-a'").fetchone()[0] == "a.xlsx"
        assert conn.execute("SELECT value FROM meta WHERE key='relational_snapshot_dirty'").fetchone()[0] == "0"


def test_unknown_legacy_group_marks_relational_snapshot_dirty(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["futureUnknownData"] = {"value": 1}
    db.save(state, "legacy_unknown")
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT value FROM meta WHERE key='relational_snapshot_dirty'").fetchone()[0] == "1"
