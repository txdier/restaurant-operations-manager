import sqlite3
from pathlib import Path

import pytest

from restaurant_manager.database import Database
from restaurant_manager.management_v6 import (
    create_reminder_v6,
    finish_reminder_v6,
    generate_payroll_v6,
    get_payroll_v6,
    list_reminders_v6,
    save_payroll_v6,
    save_stocktake_v6,
    stocktake_form_v6,
    upsert_employee_v6,
    upsert_supplier_v6,
)
from restaurant_manager.repositories_v6 import V6Repository


def test_stocktake_uses_previous_actual_and_updates_same_date_kind(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = repo.upsert_product({"name": "啤酒", "category": "酒水", "brand": "", "spec": "", "unit": "箱", "stocktake": True, "reminder": False, "active": True})

    first_form = stocktake_form_v6(db, "2026-08-20", "月底盘点")
    assert first_form["rows"][0]["previous"] == 0
    save_stocktake_v6(db, {"date": "2026-08-20", "kind": "月底盘点", "rows": [{"productId": product["id"], "previous": 0, "actual": 8, "note": "首次"}]})

    second_form = stocktake_form_v6(db, "2026-08-27", "临时盘点")
    row = next(item for item in second_form["rows"] if item["productId"] == product["id"])
    assert row["previous"] == 8
    save_stocktake_v6(db, {"date": "2026-08-27", "kind": "临时盘点", "rows": [{"productId": product["id"], "previous": 8, "actual": 5, "note": "复盘"}]})
    save_stocktake_v6(db, {"date": "2026-08-27", "kind": "临时盘点", "rows": [{"productId": product["id"], "previous": 8, "actual": 6, "note": "修正"}]})

    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM stocktakes_v6").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM stocktake_lines_v6").fetchone()[0] == 2
        latest = conn.execute("SELECT actual_quantity,note FROM stocktake_lines_v6 ORDER BY id DESC LIMIT 1").fetchone()
        assert latest == (6.0, "修正")


def test_repeating_reminder_rolls_forward_and_one_time_finishes(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = repo.upsert_product({"name": "抽纸", "category": "纸品类", "brand": "", "spec": "", "unit": "包", "stocktake": True, "reminder": True, "active": True})

    recurring = create_reminder_v6(db, {"name": "抽纸补货", "productId": product["id"], "date": "2026-08-27", "cycle": 14})
    rolled = finish_reminder_v6(db, recurring["id"])
    assert rolled["date"] == "2026-09-10"
    assert rolled["done"] is False

    once = create_reminder_v6(db, {"name": "临时补货", "productId": product["id"], "date": "2026-08-27", "cycle": 0})
    finished = finish_reminder_v6(db, once["id"])
    assert finished["done"] is True
    result = list_reminders_v6(db)
    assert result["summary"]["done"] == 1


def test_payroll_snapshot_does_not_change_when_employee_salary_changes(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    employee = upsert_employee_v6(db, {"name": "测试厨师", "role": "厨师", "salary": 6000, "startDate": "2025-01-01", "active": True})
    generated = generate_payroll_v6(db, "2026-08")
    generated_row = next(row for row in generated["rows"] if row["employeeId"] == employee["id"])
    assert generated_row["standard"] == 6000

    upsert_employee_v6(db, {**employee, "salary": 6500})
    existing = get_payroll_v6(db, "2026-08")
    existing_row = next(row for row in existing["rows"] if row["employeeId"] == employee["id"])
    assert existing_row["standard"] == 6000

    edited_rows = [
        {**row, "amount": 6200, "note": "奖金"} if row["employeeId"] == employee["id"] else row
        for row in existing["rows"]
    ]
    confirmed = save_payroll_v6(db, {"month": "2026-08", "confirmed": True, "rows": edited_rows})
    confirmed_row = next(row for row in confirmed["rows"] if row["employeeId"] == employee["id"])
    assert confirmed["confirmed"] is True
    assert confirmed_row["amount"] == 6200
    with pytest.raises(ValueError):
        generate_payroll_v6(db, "2026-08")

    unconfirmed = save_payroll_v6(db, {"month": "2026-08", "confirmed": False, "rows": confirmed["rows"]})
    assert unconfirmed["confirmed"] is False
    regenerated = generate_payroll_v6(db, "2026-08")
    regenerated_row = next(row for row in regenerated["rows"] if row["employeeId"] == employee["id"])
    assert regenerated_row["standard"] == 6500


def test_supplier_upsert_preserves_one_relational_row(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    first = upsert_supplier_v6(db, {"name": "本地菜商", "contact": "王师傅", "phone": "123", "qualification": "", "note": "", "active": True})
    second = upsert_supplier_v6(db, {**first, "phone": "456", "active": False})
    assert second["id"] == first["id"]
    assert second["phone"] == "456"
    assert second["active"] is False
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM suppliers_v6").fetchone()[0] == 1
