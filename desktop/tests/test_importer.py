from pathlib import Path

from openpyxl import load_workbook

from restaurant_manager.importer import apply_import, create_import_template, preview_import
from restaurant_manager.migrations import default_state


def test_template_preview_and_apply(tmp_path: Path):
    source = create_import_template(tmp_path / "import.xlsx")
    preview = preview_import(source, default_state())
    assert preview["errors"] == []
    assert preview["counts"] == {"quickExpenses": 1, "purchaseOrders": 1, "purchaseLines": 2}
    state = apply_import(preview, default_state(), True)
    assert [row["amount"] for row in state["expenses"]] == [680.0, 336.0, 64.0]
    assert len(state["products"]) == 2
    assert len(state["importBatches"]) == 1


def test_money_is_rounded_as_yuan_and_duplicate_order_is_rejected(tmp_path: Path):
    source = create_import_template(tmp_path / "import.xlsx")
    book = load_workbook(source)
    book["快速支出"]["C2"] = 1.235
    book.save(source)
    state = default_state()
    preview = preview_import(source, state)
    assert preview["quickExpenses"][0]["amount"] == 1.24
    state["expenses"].append({"id": 1, "purchaseNo": "CG-202608-001"})
    duplicate = preview_import(source, state)
    assert any("不能重复导入" in error for error in duplicate["errors"])
