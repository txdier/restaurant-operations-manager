from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from .version import APP_ID


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


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


def apply_update(package: Path, install_dir: Path, pid: int = 0) -> None:
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
        if executable.exists() and os.name == "nt":
            subprocess.Popen([str(executable)], cwd=str(install_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description="餐馆经营管理系统更新程序")
    parser.add_argument("package", type=Path)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--pid", type=int, default=0)
    args = parser.parse_args()
    try:
        apply_update(args.package.resolve(), args.install_dir.resolve(), args.pid)
        return 0
    except Exception as error:
        print(f"更新失败：{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
