import json
import zipfile
from pathlib import Path

from restaurant_manager.updater import apply_update, sha256


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
    apply_update(package, install)
    assert (install / "RestaurantManager.exe").read_bytes() == b"new"
    assert json.loads((install / "app-manifest.json").read_text(encoding="utf-8"))["version"] == "1.0.1"
