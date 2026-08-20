import zipfile
from pathlib import Path

import pytest

from restaurant_manager.database import Database
from restaurant_manager.migration_package import export_migration_package, import_migration_package, inspect_migration_package


def test_migration_package_round_trip(tmp_path: Path) -> None:
    source_db = Database(tmp_path / "source.db")
    state = source_db.load()
    state["expenses"] = [{"id": 9, "date": "2026-08-20", "mode": "快速记账", "category": "装修", "item": "后厨改造", "amount": 8800, "handler": "老板", "status": "有效"}]
    state["settings"]["storeName"] = "迁移测试餐馆"
    source_db.save(state, "test_seed")

    package = tmp_path / "migration.zip"
    manifest = export_migration_package(source_db, package)
    assert package.exists()
    assert manifest["format"] == "restaurant-manager-migration"
    inspected = inspect_migration_package(package)
    assert inspected["database"]["sha256"] == manifest["database"]["sha256"]

    target_db = Database(tmp_path / "target.db")
    import_migration_package(target_db, package, tmp_path / "safety")
    restored = target_db.load()
    assert restored["settings"]["storeName"] == "迁移测试餐馆"
    assert restored["expenses"][0]["item"] == "后厨改造"
    assert list((tmp_path / "safety").glob("restaurant_*_before_migration.db"))


def test_migration_package_rejects_tampered_database(tmp_path: Path) -> None:
    database = Database(tmp_path / "source.db")
    package = tmp_path / "migration.zip"
    export_migration_package(database, package)
    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(package, "r") as src, zipfile.ZipFile(broken, "w") as dst:
        dst.writestr("manifest.json", src.read("manifest.json"))
        dst.writestr("restaurant.db", src.read("restaurant.db") + b"tampered")
    with pytest.raises(ValueError, match="校验失败"):
        inspect_migration_package(broken)
