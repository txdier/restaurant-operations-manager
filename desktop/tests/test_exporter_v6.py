import csv
import zipfile
from pathlib import Path

from restaurant_manager.database import Database
from restaurant_manager.exporter_v6 import export_csv_zip_v6, export_expense_query_csv_v6
from restaurant_manager.storage_diagnostics_v6 import storage_status


def _seed(db: Database):
    state = db.load()
    state["expenses"] = [
        {"id": 1, "date": "2026-08-26", "mode": "快速记账", "category": "耗材", "item": "纸", "amount": 5.01, "handler": "甲", "status": "有效", "note": "旧"},
        {"id": 2, "date": "2026-08-27", "mode": "快速记账", "category": "耗材", "item": "盒", "amount": 20.02, "handler": "乙", "status": "有效", "note": "新"},
        {"id": 3, "date": "2026-08-27", "mode": "快速记账", "category": "食材", "item": "肉", "amount": 30.03, "handler": "乙", "status": "已作废", "note": ""},
    ]
    state["incomeRecords"] = [{"id": 10, "date": "2026-08-27", "entryMode": "day", "periodStart": "2026-08-27", "periodEnd": "2026-08-27", "dineIn": 100.01, "chess": 2.02, "delivery": 3.03, "note": ""}]
    db.save(state, "seed_export")


def test_expense_query_export_uses_relational_filters_and_sort(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    target = tmp_path / "expenses.csv"
    export_expense_query_csv_v6(db, target, category="耗材", status="有效", sort_by="amount", sort_order="desc")

    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:5] == ["日期", "方式", "类别", "项目", "金额"]
    assert len(rows) == 3
    assert rows[1][3] == "盒"
    assert rows[1][4] == "20.02"
    assert rows[2][3] == "纸"


def test_full_csv_zip_exports_relational_datasets_without_legacy_payload(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    target = tmp_path / "all.zip"
    export_csv_zip_v6(db, target, start="2026-08-27", end="2026-08-27")

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        assert "支出记录.csv" in names
        assert "收入记录.csv" in names
        expense_text = archive.read("支出记录.csv").decode("utf-8-sig")
        assert "盒" in expense_text
        assert "纸" not in expense_text
        assert "30.03" in expense_text


def test_storage_status_reports_relational_counts_and_integrity(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    _seed(db)
    result = storage_status(db, verify=True)
    assert result["schemaVersion"] == 7
    assert result["relationalAvailable"] is True
    assert result["relationalDirty"] is False
    assert result["appStatePresent"] is False
    assert result["counts"]["expenses_v6"] == 3
    assert result["integrity"] == "ok"
    assert result["foreignKeyErrors"] == 0
    assert result["verified"] is True
