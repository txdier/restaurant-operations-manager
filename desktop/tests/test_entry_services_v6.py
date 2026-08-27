import sqlite3
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.product_service_v6 import product_has_history_v6, replace_product_unit_v6, set_product_active_v6
from restaurant_manager.purchase_service_v6 import create_purchase_v6
from restaurant_manager.repositories_v6 import V6Repository


def _product(repo: V6Repository, name="五花肉", unit="kg"):
    return repo.upsert_product({
        "name": name,
        "category": "食材",
        "brand": "",
        "spec": "",
        "unit": unit,
        "stocktake": True,
        "reminder": True,
        "active": True,
    })


def test_purchase_is_created_in_one_transaction_with_cent_rounding(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = _product(repo)

    result = create_purchase_v6(db, {
        "date": "2026-08-27",
        "handler": "张师傅",
        "note": "晨间采购",
        "lines": [{"productId": product["id"], "qty": 0.375, "priceYuan": "28.50"}],
    })

    assert result["lineCount"] == 1
    assert result["amount"] == 10.69
    assert result["purchaseNo"].startswith("CG-20260827-")
    with sqlite3.connect(db.path) as conn:
        row = conn.execute(
            "SELECT amount_cents,unit_price_cents,quantity,unit_snapshot,product_id,purchase_no FROM expenses_v6"
        ).fetchone()
        assert row[:5] == (1069, 2850, 0.375, "kg", product["id"])
        assert row[5] == result["purchaseNo"]

    state = db.load()
    expense = state["expenses"][0]
    assert expense["amount"] == 10.69
    assert expense["price"] == 28.5
    assert expense["productId"] == product["id"]
    assert expense["purchaseNo"] == result["purchaseNo"]


def test_product_unit_replacement_preserves_history_and_closes_old_reminders(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = _product(repo, name="食用油", unit="桶")
    repo.create_expense({
        "date": "2026-08-20",
        "mode": "详细采购",
        "category": "食材",
        "item": "食用油 1桶",
        "amountYuan": "120.00",
        "handler": "甲",
        "productId": product["id"],
        "qty": 1,
        "unit": "桶",
        "priceYuan": "120.00",
    })
    state = db.load()
    state["reminders"] = [{"id": 1, "name": "食用油补货", "product": "食用油", "date": "2026-08-28", "cycle": 7, "done": False}]
    db.save(state, "seed_reminder")

    assert product_has_history_v6(db, product["id"]) is True
    result = replace_product_unit_v6(db, {
        "id": product["id"],
        "name": "食用油",
        "category": "食材",
        "brand": "",
        "spec": "",
        "unit": "瓶",
        "stocktake": True,
        "reminder": True,
    })

    new_id = result["newProduct"]["id"]
    with sqlite3.connect(db.path) as conn:
        old = conn.execute("SELECT unit,active,reminder_enabled FROM products_v6 WHERE id=?", (product["id"],)).fetchone()
        new = conn.execute("SELECT unit,active FROM products_v6 WHERE id=?", (new_id,)).fetchone()
        historical = conn.execute("SELECT product_id,unit_snapshot FROM expenses_v6 LIMIT 1").fetchone()
        reminder = conn.execute("SELECT done FROM reminders_v6 WHERE id=1").fetchone()
    assert old == ("桶", 0, 0)
    assert new == ("瓶", 1)
    assert historical == (product["id"], "桶")
    assert reminder == (1,)


def test_deactivating_product_closes_pending_reminders(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    repo = V6Repository(db)
    product = _product(repo, name="抽纸", unit="包")
    state = db.load()
    state["reminders"] = [{"id": 7, "name": "抽纸补货", "product": "抽纸", "date": "2026-08-28", "cycle": 14, "done": False}]
    db.save(state, "seed_reminder")

    item = set_product_active_v6(db, product["id"], False)
    assert item["active"] is False
    assert item["reminder"] is False
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT done FROM reminders_v6 WHERE id=7").fetchone() == (1,)
