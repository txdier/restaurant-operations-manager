from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from .version import APP_ID


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Programs" / "RestaurantManager"
    return Path.home() / "AppData" / "Local" / "Programs" / "RestaurantManager"


def find_adjacent_package(directory: Path) -> Optional[Path]:
    packages = sorted(directory.glob("RestaurantManager-Update-*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    return packages[0] if packages else None


def select_update_package() -> Optional[Path]:
    if os.name != "nt":
        return None
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$dialog=New-Object System.Windows.Forms.OpenFileDialog;"
        "$dialog.Title='Select Restaurant Manager update package';"
        "$dialog.Filter='Restaurant Manager update (*.zip)|RestaurantManager-Update-*.zip|ZIP files (*.zip)|*.zip';"
        "if($dialog.ShowDialog() -eq 'OK'){$dialog.FileName}"
    )
    result = subprocess.check_output(
        ["powershell.exe", "-STA", "-NoProfile", "-Command", script],
        text=True,
        creationflags=0x08000000,
    ).strip()
    return Path(result) if result else None


def show_message(message: str, error: bool = False) -> None:
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "餐馆经营管理系统更新", 0x10 if error else 0x40)
    else:
        print(message)


def wait_for_pid(pid: int, timeout: int = 30) -> None:
    if pid <= 0:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.5)
    raise RuntimeError("餐馆经营管理系统仍在运行，请关闭后重试更新")


def apply_update(package: Path, install_dir: Path, pid: int = 0, restart: bool = True) -> None:
    wait_for_pid(pid)
    with tempfile.TemporaryDirectory(prefix="restaurant-update-") as temp:
        temp_dir = Path(temp)
        with zipfile.ZipFile(package) as archive:
            archive.extractall(temp_dir)
        manifest = json.loads((temp_dir / "update.json").read_text(encoding="utf-8"))
        if manifest.get("appId") != APP_ID:
            raise ValueError("更新包不属于本程序")
        installed_manifest = install_dir / "app-manifest.json"
        installed = json.loads(installed_manifest.read_text(encoding="utf-8")) if installed_manifest.exists() else {"version": "0.0.0"}
        if version_tuple(manifest["version"]) <= version_tuple(installed.get("version", "0.0.0")):
            raise ValueError("更新包版本不高于当前版本")
        if version_tuple(installed.get("version", "0.0.0")) < version_tuple(manifest.get("minVersion", "0.0.0")):
            raise ValueError("当前版本过旧，不能直接使用此增量更新包")
        payload = temp_dir / "payload"
        for entry in manifest["files"]:
            source = payload / entry["path"]
            if sha256(source) != entry["sha256"]:
                raise ValueError(f"更新文件校验失败：{entry['path']}")
        rollback = install_dir.parent / f"{install_dir.name}.rollback"
        if rollback.exists():
            shutil.rmtree(rollback)
        if install_dir.exists():
            shutil.copytree(install_dir, rollback)
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
            for entry in manifest["files"]:
                source = payload / entry["path"]
                target = install_dir / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            installed_manifest.write_text(json.dumps({"appId": APP_ID, "version": manifest["version"]}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            if rollback.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
                shutil.copytree(rollback, install_dir)
            raise
        executable = install_dir / "RestaurantManager.exe"
        if restart and executable.exists() and os.name == "nt":
            subprocess.Popen([str(executable)], cwd=str(install_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description="餐馆经营管理系统更新程序")
    parser.add_argument("package", type=Path, nargs="?")
    parser.add_argument("--install-dir", type=Path, default=default_install_dir())
    parser.add_argument("--pid", type=int, default=0)
    args = parser.parse_args()
    try:
        package = args.package or find_adjacent_package(Path(sys.executable).resolve().parent) or select_update_package()
        if package is None:
            raise ValueError("未选择更新包。请下载 RestaurantManager-Update-x.y.z.zip 后重试。")
        apply_update(package.resolve(), args.install_dir.resolve(), args.pid)
        show_message("更新完成，餐馆经营管理系统即将启动。")
        return 0
    except Exception as error:
        print(f"更新失败：{error}")
        show_message(f"更新失败：{error}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
