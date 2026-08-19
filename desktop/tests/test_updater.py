import json
import os
import zipfile
from pathlib import Path

from restaurant_manager.updater import apply_update, find_adjacent_package, sha256


def test_incremental_update_preserves_unrelated_data(tmp_path: Path):
    install = tmp_path / "RestaurantManager"
    install.mkdir()
    (install / "RestaurantManager.exe").write_bytes(b"old")
    (install / "app-manifest.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    payload = tmp_path / "new.exe"
    payload.write_bytes(b"new")
    package = tmp_path / "update.zip"
    manifest = {"appId": "cn.restaurant.manager", "version": "1.0.1", "minVersion": "1.0.0", "files": [{"path": "RestaurantManager.exe", "sha256": sha256(payload), "size": 3}]}
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("update.json", json.dumps(manifest))
        archive.write(payload, "payload/RestaurantManager.exe")
    apply_update(package, install, restart=False)
    assert (install / "RestaurantManager.exe").read_bytes() == b"new"
    assert json.loads((install / "app-manifest.json").read_text(encoding="utf-8"))["version"] == "1.0.1"


def test_latest_adjacent_update_package_is_selected(tmp_path: Path):
    older = tmp_path / "RestaurantManager-Update-1.0.1.zip"
    newer = tmp_path / "RestaurantManager-Update-1.0.2.zip"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    assert find_adjacent_package(tmp_path) == newer
