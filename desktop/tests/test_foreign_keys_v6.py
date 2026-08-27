import sqlite3
from pathlib import Path

from restaurant_manager.database import Database


def test_runtime_connections_enable_foreign_keys_and_replace_child_rows(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["salesRecords"] = [{
        "id": 1,
        "date": "2026-08-27",
        "rows": [
            {"categoryId": 1, "category": "主食", "qty": 2, "amount": 20},
            {"categoryId": 2, "category": "酒水", "qty": 3, "amount": 30},
        ],
    }]
    db.save(state, "sales_seed")

    with db.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sales_lines_v6 WHERE sales_record_id=1").fetchone()[0] == 2

    state = db.load()
    state["salesRecords"][0]["rows"] = [{"categoryId": 1, "category": "主食", "qty": 1, "amount": 10}]
    db.save(state, "sales_replace")

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales_lines_v6 WHERE sales_record_id=1").fetchone()[0] == 1
        assert conn.execute("SELECT amount_cents FROM sales_lines_v6 WHERE sales_record_id=1").fetchone()[0] == 1000


def test_stocktake_and_payroll_children_do_not_accumulate_on_replace(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["stocktakes"] = [{"id": 5, "date": "2026-08-27", "kind": "临时盘点", "rows": [{"productId": None, "product": "A", "unit": "个", "previous": 2, "actual": 1, "change": -1, "note": ""}]}]
    state["payrolls"] = [{"month": "2026-08", "confirmed": False, "rows": [{"employeeId": None, "name": "甲", "role": "员工", "standard": 1000, "amount": 900, "note": ""}]}]
    db.save(state, "children_seed")

    state = db.load()
    state["stocktakes"][0]["rows"][0]["actual"] = 3
    state["stocktakes"][0]["rows"][0]["change"] = 1
    state["payrolls"][0]["rows"][0]["amount"] = 800
    db.save(state, "children_replace")

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM stocktake_lines_v6 WHERE stocktake_id=5").fetchone()[0] == 1
        assert conn.execute("SELECT actual_quantity FROM stocktake_lines_v6 WHERE stocktake_id=5").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM payroll_lines_v6").fetchone()[0] == 1
        assert conn.execute("SELECT actual_salary_cents FROM payroll_lines_v6").fetchone()[0] == 80000
