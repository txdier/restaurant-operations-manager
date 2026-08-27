import sqlite3
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.repositories_v6 import V6Repository
from restaurant_manager.storage_v6 import state_to_v6


def _seed(db: Database, state):
    db.save(state, "seed")
    with db.connect() as conn:
        state_to_v6(conn, db.load())
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('relational_snapshot_dirty','0')")
        conn.commit()


def test_expense_repository_stores_cents_and_mirrors_legacy_state(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [{"id": 1, "name": "耗材", "active": True}]
    _seed(db, state)
    repo = V6Repository(db)

    created = repo.create_expense({
        "date": "2026-08-27",
        "mode": "快速记账",
        "category": "耗材",
        "item": "抽纸",
        "amountYuan": "12.34",
        "handler": "甲",
        "status": "有效",
    })

    assert created["amount"] == 12.34
    assert db.load()["expenses"][0]["id"] == created["id"]
    with sqlite3.connect(db.path) as conn:
        row = conn.execute("SELECT amount_cents,category_id FROM expenses_v6 WHERE id=?", (created["id"],)).fetchone()
        assert row == (1234, 1)


def test_expense_query_uses_filter_sort_and_pagination(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [{"id": 1, "name": "耗材", "active": True}, {"id": 2, "name": "食材", "active": True}]
    _seed(db, state)
    repo = V6Repository(db)
    repo.create_expense({"date": "2026-08-26", "category": "耗材", "item": "纸", "amountYuan": "5.00", "handler": "甲"})
    repo.create_expense({"date": "2026-08-27", "category": "耗材", "item": "盒", "amountYuan": "20.00", "handler": "乙"})
    repo.create_expense({"date": "2026-08-27", "category": "食材", "item": "肉", "amountYuan": "30.00", "handler": "乙"})

    result = repo.list_expenses(category="耗材", sort_by="amount", sort_order="desc", page=1, page_size=1)
    assert result["total"] == 2
    assert result["totalPages"] == 2
    assert result["amountTotal"] == 25
    assert result["items"][0]["amount"] == 20


def test_update_and_void_expense_keep_legacy_mirror_consistent(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    item = repo.create_expense({"date": "2026-08-27", "category": "其他", "item": "杂费", "amountYuan": "9.99", "handler": "甲"})

    updated = repo.update_expense(item["id"], {"amountYuan": "10.01", "handler": "乙"})
    assert updated["amount"] == 10.01
    assert updated["handler"] == "乙"
    voided = repo.void_expense(item["id"])
    assert voided["status"] == "已作废"
    mirror = next(row for row in db.load()["expenses"] if row["id"] == item["id"])
    assert mirror["amount"] == 10.01
    assert mirror["status"] == "已作废"


def test_product_repository_upsert_and_search(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = repo.upsert_product({
        "name": "静音抽纸",
        "category": "耗材",
        "brand": "测试",
        "spec": "3层",
        "unit": "包",
        "stocktake": True,
        "reminder": False,
        "active": True,
    })
    assert product["id"] > 0
    assert repo.list_products("抽纸", active=True)[0]["name"] == "静音抽纸"
    mirror = next(row for row in db.load()["products"] if row["id"] == product["id"])
    assert mirror["unit"] == "包"


def test_income_repository_upsert_uses_integer_cents(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    income = repo.upsert_income({
        "date": "2026-08-27",
        "entryMode": "day",
        "dineIn": "100.01",
        "chess": "20.02",
        "delivery": "3.03",
        "note": "测试",
    })
    assert income["dineIn"] == 100.01
    with sqlite3.connect(db.path) as conn:
        row = conn.execute("SELECT dine_in_cents,chess_cents,delivery_cents FROM income_records_v6 WHERE id=?", (income["id"],)).fetchone()
        assert row == (10001, 2002, 303)
    mirror = next(row for row in db.load()["incomeRecords"] if row["id"] == income["id"])
    assert mirror["delivery"] == 3.03


def test_dashboard_summary_uses_relational_aggregates(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    repo.upsert_income({"date": "2026-08-27", "entryMode": "day", "dineIn": "100", "chess": "0", "delivery": "0"})
    repo.create_expense({"date": "2026-08-27", "category": "其他", "item": "杂费", "amountYuan": "25.50", "handler": "甲"})
    repo.create_expense({"date": "2026-08-26", "category": "其他", "item": "旧杂费", "amountYuan": "10.00", "handler": "甲"})

    result = repo.dashboard_summary("2026-08-27", "2026-08-01", "2026-08-31")
    assert result["todayIncome"] == 100
    assert result["todayExpense"] == 25.5
    assert result["monthExpense"] == 35.5
    assert result["monthBalance"] == 64.5
