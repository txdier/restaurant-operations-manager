from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .database import Database
from .version import APP_NAME, APP_VERSION, DATA_SCHEMA_VERSION

MIGRATION_FORMAT = "restaurant-manager-migration"
MIGRATION_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "restaurant.db"
MAX_DATABASE_SIZE = 1024 * 1024 * 1024
MAX_MANIFEST_SIZE = 128 * 1024


def _sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _manifest(schema_version: int, database_hash: str) -> Dict[str, Any]:
    return {
        "format": MIGRATION_FORMAT,
        "formatVersion": MIGRATION_FORMAT_VERSION,
        "appName": APP_NAME,
        "appVersion": APP_VERSION,
        "schemaVersion": schema_version,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "database": {"path": DATABASE_NAME, "sha256": database_hash},
    }


def export_migration_package(database: Database, target: Path) -> Dict[str, Any]:
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restaurant-migration-export-") as temp_dir:
        snapshot = database.backup(Path(temp_dir), "migration")
        with snapshot.open("rb") as handle:
            database_hash = _sha256_stream(handle)
        manifest = _manifest(DATA_SCHEMA_VERSION, database_hash)
        with zipfile.ZipFile(str(target), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(str(snapshot), DATABASE_NAME)
    return manifest


def inspect_migration_package(source: Path) -> Dict[str, Any]:
    if not source.exists() or source.suffix.lower() != ".zip":
        raise ValueError("请选择有效的 .zip 系统迁移包")
    if not zipfile.is_zipfile(str(source)):
        raise ValueError("迁移包不是有效的 ZIP 文件")
    with zipfile.ZipFile(str(source), "r") as archive:
        names = set(archive.namelist())
        if MANIFEST_NAME not in names or DATABASE_NAME not in names:
            raise ValueError("迁移包缺少 manifest.json 或 restaurant.db")
        if archive.getinfo(MANIFEST_NAME).file_size > MAX_MANIFEST_SIZE:
            raise ValueError("迁移包清单大小异常")
        if archive.getinfo(DATABASE_NAME).file_size > MAX_DATABASE_SIZE:
            raise ValueError("迁移包数据库超过 1 GB，已拒绝导入")
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("迁移包清单无法读取") from error
        if manifest.get("format") != MIGRATION_FORMAT:
            raise ValueError("该文件不是本系统生成的迁移包")
        if int(manifest.get("formatVersion", 0)) != MIGRATION_FORMAT_VERSION:
            raise ValueError("暂不支持该迁移包格式，请先升级软件")
        try:
            schema_version = int(manifest.get("schemaVersion", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("迁移包数据版本无效") from error
        if schema_version <= 0:
            raise ValueError("迁移包数据版本无效")
        if schema_version > DATA_SCHEMA_VERSION:
            raise ValueError("迁移包来自更高的数据版本，请先把当前软件升级到不低于来源电脑的版本后再导入")
        expected_hash = str(manifest.get("database", {}).get("sha256", "")).lower()
        if len(expected_hash) != 64:
            raise ValueError("迁移包数据库校验信息缺失")
        with archive.open(DATABASE_NAME, "r") as database_stream:
            actual_hash = _sha256_stream(database_stream)
        if actual_hash != expected_hash:
            raise ValueError("迁移包数据库校验失败，文件可能不完整或已损坏")
    return manifest


def import_migration_package(database: Database, source: Path, safety_dir: Path) -> Dict[str, Any]:
    manifest = inspect_migration_package(source)
    safety_dir.mkdir(parents=True, exist_ok=True)
    safety_backup = database.backup(safety_dir, "before_migration")
    with tempfile.TemporaryDirectory(prefix="restaurant-migration-import-") as temp_dir:
        candidate = Path(temp_dir) / DATABASE_NAME
        with zipfile.ZipFile(str(source), "r") as archive:
            with archive.open(DATABASE_NAME, "r") as src, candidate.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        database.restore(candidate)
    return {"manifest": manifest, "safetyBackup": str(safety_backup)}
