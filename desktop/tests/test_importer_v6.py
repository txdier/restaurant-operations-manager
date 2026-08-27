import sqlite3
from pathlib import Path

from openpyxl import Workbook

from restaurant_manager.database import Database
from restaurant_manager.importer_v6 import DETAIL_HEADERS, QUICK_HEADERS, apply_import_v6, preview_import_v6, public_preview


def _workbook(path: Path):
    book = Workbook()
    quick = book.active
    quick.title = "快速支出"
    detail = book.create_sheet("详细采购")
    quick.append(QUICK_HEADERS)
    detail.append(DETAIL_HEADERS)
    return book, quick, detail


def test_preview_and_apply_import_use_relational_lookups_and_integer_cents(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [
        {"id": 1, "name": "耗材", "active": True},
        {"id": 2, "name": "食材", "active": True},
    ]
    state["products"] = [{"id": 10, "name": "五花肉", "category": "食材", "brand": "", "spec": "", "unit": "kg", "stocktake": True, "reminder": False, "active": True}]
    db.save(state, "seed_import")

    path = tmp_path / "import.xlsx"
    book, quick, detail = _workbook(path)
    quick.append(["2026-08-27", "耗材", 12.34, "甲", "抽纸"])
    detail.append(["CG-001", "2026-08-27", "五花肉", "食材", 0.375, "kg", 28.50, "乙", "晨购"])
    detail.append(["CG-001", "2026-08-27", "土豆", "食材", 2, "kg", 3.20, "乙", "晨购"])
    book.save(path)

    preview = preview_import_v6(path, db)
    public = public_preview(preview)
    assert public["errors"] == []
    assert public["counts"] == {"quickExpenses": 1, "duplicateQuickExpenses": 0, "purchaseOrders": 1, "purchaseLines": 2}
    assert public["unknownProducts"] == [{"name": "土豆", "unit": "kg", "category": "食材"}]
    assert "_internal" not in public

    result = apply_import_v6(preview, db, create_unknown_products=True)
    assert result["batchId"]
    with sqlite3.connect(db.path) as conn:
        quick_row = conn.execute("SELECT amount_cents,import_batch_id FROM expenses_v6 WHERE mode='快速记账'").fetchone()
        assert quick_row[0] == 1234
        detail_rows = conn.execute("SELECT product_name_snapshot,quantity,unit_price_cents,amount_cents FROM expenses_v6 WHERE purchase_no='CG-001' ORDER BY id").fetchall()
        assert detail_rows[0] == ("五花肉", 0.375, 2850, 1069)
        assert detail_rows[1] == ("土豆", 2.0, 320, 640)
        assert conn.execute("SELECT COUNT(*) FROM products_v6 WHERE name='土豆' AND unit='kg'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM import_batches_v6 WHERE id=?", (result["batchId"],)).fetchone()[0] == 1

    loaded = db.load()
    assert len([row for row in loaded["expenses"] if row.get("purchaseNo") == "CG-001"]) == 2


def test_preview_detects_existing_quick_and_purchase_duplicates(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [{"id": 1, "name": "耗材", "active": True}]
    state["products"] = [{"id": 10, "name": "抽纸", "category": "耗材", "brand": "", "spec": "", "unit": "包", "stocktake": True, "reminder": False, "active": True}]
    state["expenses"] = [
        {"id": 1, "date": "2026-08-27", "mode": "快速记账", "category": "耗材", "item": "水电", "amount": 10, "handler": "甲", "status": "有效", "note": "水电"},
        {"id": 2, "date": "2026-08-27", "mode": "详细采购", "category": "耗材", "item": "抽纸 1包", "amount": 5, "handler": "乙", "status": "有效", "purchaseNo": "CG-OLD", "productId": 10, "qty": 1, "unit": "包", "price": 5},
    ]
    db.save(state, "seed_duplicates")

    path = tmp_path / "duplicate.xlsx"
    book, quick, detail = _workbook(path)
    quick.append(["2026-08-27", "耗材", 10, "甲", "水电"])
    detail.append(["CG-OLD", "2026-08-27", "抽纸", "耗材", 1, "包", 5, "乙", ""])
    book.save(path)

    preview = preview_import_v6(path, db)
    assert preview["counts"]["quickExpenses"] == 0
    assert preview["counts"]["duplicateQuickExpenses"] == 1
    assert preview["duplicateQuickExpenses"][0]["reason"] == "系统已有相同记录"
    assert any("CG-OLD" in error for error in preview["errors"])


def test_import_can_explicitly_keep_duplicate_quick_expense(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    state = db.load()
    state["expenseCategories"] = [{"id": 1, "name": "耗材", "active": True}]
    state["expenses"] = [{"id": 1, "date": "2026-08-27", "mode": "快速记账", "category": "耗材", "item": "米油", "amount": 20, "handler": "甲", "status": "有效", "note": ""}]
    db.save(state, "seed_duplicate_allowed")

    path = tmp_path / "duplicate-allowed.xlsx"
    book, quick, _ = _workbook(path)
    quick.append(["2026-08-27", "耗材", 20, "甲", "米油"])
    book.save(path)
    preview = preview_import_v6(path, db)
    assert preview["counts"]["duplicateQuickExpenses"] == 1

    apply_import_v6(preview, db, create_unknown_products=False, import_duplicate_quick_expenses=True)
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM expenses_v6 WHERE expense_date='2026-08-27' AND amount_cents=2000 AND handler='甲'").fetchone()[0] == 2
