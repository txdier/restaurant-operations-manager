from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator

from .migrations import migrate_database, migrate_state
from .paths import database_path, default_backup_dir
from .version import DATA_SCHEMA_VERSION


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        safety = self._migration_backup()
        try:
            with self.connect() as conn:
                migrate_database(conn)
        except Exception:
            if safety:
                shutil.copy2(safety, self.path)
            raise

    def _stored_schema_version(self) -> int:
        if not self.path.exists() or not self.path.stat().st_size:
            return DATA_SCHEMA_VERSION
        try:
            with self.connect() as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "meta" in tables:
                    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                    if row:
                        return int(row[0])
                if "app_state" in tables:
                    row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
                    return int(json.loads(row[0]).get("schemaVersion", 1)) if row else 1
                return 1
        except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
            return 1

    def _migration_backup(self) -> Path | None:
        old_version = self._stored_schema_version()
        if old_version >= DATA_SCHEMA_VERSION or not self.path.exists() or not self.path.stat().st_size:
            return None
        root = self.path.parent / "backups"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        target = root / f"restaurant_{stamp}_before_schema_v{old_version}_to_v{DATA_SCHEMA_VERSION}.db"
        with sqlite3.connect(str(self.path)) as source, sqlite3.connect(str(target)) as dest:
            source.backup(dest)
        return target

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=15)
        try:
            yield conn
        finally:
            conn.close()

    def load(self) -> Dict[str, Any]:
        with self.lock, self.connect() as conn:
            row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
            if row is None:
                raise RuntimeError("本地数据库缺少主数据")
            return migrate_state(json.loads(row[0]))

    def save(self, state: Dict[str, Any], event: str = "save_state") -> Dict[str, Any]:
        with self.lock, self.connect() as conn:
            current_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
            current = json.loads(current_row[0]) if current_row else {}
            password_hash = current.get("settings", {}).get("passwordHash")
            state = migrate_state(state)
            if password_hash and not state.get("settings", {}).get("passwordHash"):
                state["settings"]["passwordHash"] = password_hash
            payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE app_state SET payload=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (payload,))
            conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", (event, "{}"))
            conn.commit()
        return state

    def backup(self, target_dir: Path | None = None, kind: str = "manual") -> Path:
        target_dir = target_dir or default_backup_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        target = target_dir / f"restaurant_{stamp}_{kind}.db"
        with self.lock, self.connect() as source, sqlite3.connect(str(target)) as dest:
            source.backup(dest)
        return target

    def restore(self, source: Path) -> None:
        if not source.exists() or source.suffix.lower() != ".db":
            raise ValueError("请选择有效的 .db 备份文件")
        safety = self.backup(source.parent, kind="before_restore")
        restore_copy = self.path.parent / ".restore-candidate.db"
        try:
            shutil.copy2(source, restore_copy)
            with closing(sqlite3.connect(str(restore_copy))) as check:
                migrate_database(check)
                row = check.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
                if row is None:
                    raise ValueError("备份中没有可恢复的数据")
                migrate_state(json.loads(row[0]))
            with self.lock:
                shutil.copy2(restore_copy, self.path)
            with self.connect() as conn:
                migrate_database(conn)
        except Exception:
            shutil.copy2(safety, self.path)
            raise
        finally:
            restore_copy.unlink(missing_ok=True)
