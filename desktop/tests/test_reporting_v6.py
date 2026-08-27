from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.reporting_v6 import ReportRepositoryV6


def _seed(db: Database):
    state = db.load()
    state["products"] = [{"id": 10, "name": "五花肉", "category": "食材", "brand": "", "spec": "", "unit": "kg", "stocktake": True, "reminder": False, "active": True}]
    state["incomeRecords"] = [
        {"id": 1, "date": "2026-08-26", "entryMode": "day", "periodStart": "2026-08-26", "periodEnd": "2026-08-26", "dineIn": 100, "chess": 5, "delivery": 5, "note": "旧"},
        {"id": 2, "date": "2026-08-27", "entryMode": "day", "periodStart": "2026-08-27", "periodEnd": "2026-08-27", "dineIn": 200, "chess": 10, "delivery": 10, "note": "新"},
    ]
    state["expenses"] = [
        {"id": 1, "date": "2026-08-26", "mode": "快速记账", "category": "耗材", "item": "纸", "amount": 20, "handler": "甲", "status": "有效"},
        {"id": 2, "date": "2026-08-27", "mode": "详细采购", "category": "食材", "item": "五花肉 2kg", "amount": 60, "handler": "乙", "status": "有效", "productId": 10, "qty": 2, "unit": "kg", "price": 30},
        {"id": 3, "date": "2026-08-27", "mode": "快速记账", "category": "其他", "item": "作废", "amount": 50, "handler": "乙", "status": "已作废"},
    ]
    state["salesRecords"] = [{"id": 1, "date": "2026-08-27", "rows": [{"categoryId": 1, "category": "主食", "qty": 2, "amount": 30}, {"categoryId": 2, "category": "酒水", "qty": 1, "amount": 10}]}]
    state["stocktakes"] = [{"id": 1, "date": "2026-08-27", "kind": "临时盘点", "rows": [{"productId": 10, "product": "五花肉", "unit": "kg", "previous": 3, "actual": 2, "change": -1, "note": "盘点"}]}]
    db.save(state, "seed_reports")


def test_report_summary_uses_active_expenses_only(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    repo = ReportRepositoryV6(db)
    result = repo.summary("2026-08-26", "2026-08-27")
    assert result == {"income": 330, "expense": 80, "balance": 250}


def test_income_sales_stock_reports_page_and_sort_in_sql(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    repo = ReportRepositoryV6(db)

    income = repo.income(start="2026-08-01", end="2026-08-31", sort_by="total", sort_order="desc", page=1, page_size=1)
    assert income["total"] == 2
    assert income["totalPages"] == 2
    assert income["items"][0]["date"] == "2026-08-27"
    assert income["items"][0]["total"] == 220

    sales = repo.sales(start="2026-08-01", end="2026-08-31", sort_by="amount", sort_order="desc", page=1, page_size=20)
    assert [row["category"] for row in sales["items"]] == ["主食", "酒水"]

    stock = repo.stock(start="2026-08-01", end="2026-08-31", keyword="五花肉", page=1, page_size=20)
    assert stock["total"] == 1
    assert stock["items"][0]["change"] == -1


def test_price_history_uses_product_id_and_snapshot_data(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    repo = ReportRepositoryV6(db)
    result = repo.prices(product_id=10, start="2026-08-01", end="2026-08-31", page=1, page_size=20)
    assert result["total"] == 1
    assert result["product"]["name"] == "五花肉"
    assert result["items"][0]["qty"] == 2
    assert result["items"][0]["price"] == 30
    assert result["summary"] == {"min": 30, "max": 30, "average": 30, "latest": 30}


def test_report_filter_options_do_not_require_loading_all_expenses(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    repo = ReportRepositoryV6(db)
    options = repo.filter_options()
    assert "甲" in options["handlers"] and "乙" in options["handlers"]
    assert options["products"][0]["name"] == "五花肉"
