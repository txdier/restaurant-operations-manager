from pathlib import Path

import pytest

from restaurant_manager.configuration_v6 import (
    bootstrap_v6,
    change_password_v6,
    patch_settings_v6,
    save_expense_categories_v6,
    save_sale_categories_v6,
    security_status_v6,
    verify_unlock_v6,
)
from restaurant_manager.database import Database


def test_bootstrap_returns_only_lightweight_configuration(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    boot = bootstrap_v6(db)
    assert set(boot) == {"settings", "saleCategories", "expenseCategories", "security"}
    assert "expenses" not in boot
    assert "incomeRecords" not in boot
    assert isinstance(boot["saleCategories"], list)
    assert isinstance(boot["expenseCategories"], list)


def test_settings_and_categories_patch_relational_configuration(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    settings = patch_settings_v6(db, {"storeName": "测试餐馆", "autoLockMinutes": 30})
    assert settings["storeName"] == "测试餐馆"
    assert settings["autoLockMinutes"] == 30

    sales = save_sale_categories_v6(db, [{"id": 1, "name": "主食调整", "active": True}])
    expenses = save_expense_categories_v6(db, [{"id": 1, "name": "食材调整", "active": True}])
    boot = bootstrap_v6(db)
    assert sales[0]["name"] == "主食调整"
    assert expenses[0]["name"] == "食材调整"
    assert boot["saleCategories"][0]["name"] == "主食调整"
    assert boot["expenseCategories"][0]["name"] == "食材调整"


def test_password_uses_security_settings_without_plaintext(tmp_path: Path):
    db = Database(tmp_path / "restaurant.db")
    assert security_status_v6(db)["hasPassword"] is False
    assert verify_unlock_v6(db, "") is True

    change_password_v6(db, "", "123456")
    status = security_status_v6(db)
    assert status["hasPassword"] is True
    assert verify_unlock_v6(db, "123456") is True
    assert verify_unlock_v6(db, "wrong-password") is False

    with pytest.raises(ValueError):
        change_password_v6(db, "wrong-password", "654321")
    change_password_v6(db, "123456", "654321")
    assert verify_unlock_v6(db, "123456") is False
    assert verify_unlock_v6(db, "654321") is True
