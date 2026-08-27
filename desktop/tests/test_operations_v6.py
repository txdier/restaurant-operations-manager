import sqlite3
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.operations_v6 import dashboard_detail_v6, get_sales_record_v6, save_sales_record_v6
from restaurant_manager.repositories_v6 import V6Repository


def test_dashboard_detail_uses_relational_aggregates(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    repo.upsert_income({"date": "2026-08-27", "entryMode": "day", "periodStart": "2026-08-27", "periodEnd": "2026-08-27", "dineIn": 100.01, "chess": 2.02, "delivery": 3.03, "note": ""})
    repo.create_expense({"date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "杂费", "amountYuan": "10.50", "handler": "甲", "status": "有效"})
    repo.create_expense({"date": "2026-08-26", "mode": "快速记账", "category": "其他", "item": "旧杂费", "amountYuan": "5.00", "handler": "甲", "status": "已作废"})

    result = dashboard_detail_v6(db, "2026-08-27")
    assert result["todayIncome"] == 105.06
    assert result["todayExpense"] == 10.5
    assert result["monthIncome"] == 105.06
    assert result["monthExpense"] == 10.5
    assert result["monthBalance"] == 94.56
    assert result["trend"][-1] == {"date": "2026-08-27", "income": 105.06, "expense": 10.5}
    assert result["categories"][0] == {"name": "其他", "amount": 10.5}


def test_sales_record_reads_daily_income_and_replaces_lines(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    repo.upsert_income({"date": "2026-08-27", "entryMode": "day", "periodStart": "2026-08-27", "periodEnd": "2026-08-27", "dineIn": 200, "chess": 20, "delivery": 30, "note": ""})

    first = save_sales_record_v6(db, {
        "date": "2026-08-27",
        "rows": [
            {"categoryId": 1, "category": "主食", "qty": 3, "amount": 100.01},
            {"categoryId": 2, "category": "小炒菜", "qty": 4, "amount": 149.99},
        ],
    })
    assert first["date"] == "2026-08-27"
    loaded = get_sales_record_v6(db, "2026-08-27")
    assert loaded["dailyIncome"] == 250
    assert len(loaded["rows"]) == 2
    assert sum(row["amount"] for row in loaded["rows"]) == 250

    second = save_sales_record_v6(db, {
        "date": "2026-08-27",
        "rows": [{"categoryId": 1, "category": "主食", "qty": 5, "amount": 250}],
    })
    assert second["id"] == first["id"]
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sales_records_v6").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sales_lines_v6").fetchone()[0] == 1
        assert conn.execute("SELECT amount_cents FROM sales_lines_v6").fetchone()[0] == 25000

    state = db.load()
    assert len(state["salesRecords"]) == 1
    assert state["salesRecords"][0]["rows"][0]["amount"] == 250
