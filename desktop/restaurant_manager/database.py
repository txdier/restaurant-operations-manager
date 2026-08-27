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
        self._initialize_safely()

    def _initialize_safely(self) -> None:
        old_version = self._stored_schema_version()
        needs_candidate = self.path.exists() and self.path.stat().st_size and old_version < DATA_SCHEMA_VERSION
        if not needs_candidate:
            with self.connect() as conn:
                migrate_database(conn)
            return

        safety = self._migration_backup(old_version)
        candidate = self.path.parent / ".migration-candidate.db"
        candidate.unlink(missing_ok=True)
        try:
            with sqlite3.connect(str(self.path)) as source, sqlite3.connect(str(candidate)) as dest:
                source.backup(dest)
            with sqlite3.connect(str(candidate), timeout=15) as conn:
                migrate_database(conn)
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise ValueError("候选数据库完整性检查失败")
                version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if not version or int(version[0]) != DATA_SCHEMA_VERSION:
                    raise ValueError("候选数据库版本校验失败")
            self._replace_from_snapshot(candidate)
        except Exception:
            # Migration happens on the candidate copy. The active database normally
            # remains untouched; the safety copy also protects against a replace
            # failure after validation.
            if safety.exists():
                self._replace_from_snapshot(safety)
            raise
        finally:
            candidate.unlink(missing_ok=True)

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

    def _migration_backup(self, old_version: int | None = None) -> Path:
        old_version = self._stored_schema_version() if old_version is None else old_version
        root = self.path.parent / "backups" / "migration"
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

    def _clear_wal_sidecars(self) -> None:
        for suffix in ("-wal", "-shm"):
            Path(str(self.path) + suffix).unlink(missing_ok=True)

    def _replace_from_snapshot(self, source: Path) -> None:
        """Replace the active database from a checked SQLite snapshot."""
        with self.lock:
            self._clear_wal_sidecars()
            shutil.copy2(source, self.path)
            self._clear_wal_sidecars()

    def load(self) -> Dict[str, Any]:
        # During phase A app_state intentionally remains the runtime source of truth.
        # v6 tables are a validated migration snapshot until per-entity APIs replace
        # the legacy whole-state save path.
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
            # Mark the migration snapshot dirty. Phase B entity repositories will
            # update relational tables directly and remove this compatibility flag.
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('relational_snapshot_dirty','1')")
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
                integrity = check.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise ValueError("备份数据库完整性检查失败")
            self._replace_from_snapshot(restore_copy)
            with self.connect() as conn:
                migrate_database(conn)
        except Exception:
            self._replace_from_snapshot(safety)
            raise
        finally:
            restore_copy.unlink(missing_ok=True)
