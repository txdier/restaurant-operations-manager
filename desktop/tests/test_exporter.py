import zipfile
from pathlib import Path

from openpyxl import load_workbook

from restaurant_manager.exporter import export_csv_zip, export_xlsx
from restaurant_manager.migrations import default_state


def test_exports_all_business_sections(tmp_path: Path):
    state = default_state()
    state["expenses"] = [{"id": 1, "date": "2026-08-19", "amount": 12.5, "item": "测试"}]
    xlsx = export_xlsx(state, tmp_path / "all.xlsx")
    assert "expenses" in load_workbook(xlsx, read_only=True).sheetnames
    archive = export_csv_zip(state, tmp_path / "all.zip")
    with zipfile.ZipFile(archive) as zf:
        assert "expenses.csv" in zf.namelist()
