import json
import sqlite3
from contextlib import closing
from pathlib import Path

import restaurant_manager.database as database_module
from restaurant_manager.database import Database


def test_schema_migration_removes_candidate_and_wal_sidecars(tmp_path: Path):
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(str(path))) as conn:
        conn.execute("CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
        conn.execute(
            "INSERT INTO app_state VALUES(1,?,CURRENT_TIMESTAMP)",
            (json.dumps({"schemaVersion": 1, "expenses": [], "incomeRecords": []}),),
        )
        conn.commit()

    Database(path)

    candidate = tmp_path / ".migration-candidate.db"
    assert not candidate.exists()
    assert not Path(str(candidate) + "-wal").exists()
    assert not Path(str(candidate) + "-shm").exists()


def test_schema_migration_clears_stale_candidate_sidecars_before_open(tmp_path: Path, monkeypatch):
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(str(path))) as conn:
        conn.execute("CREATE TABLE app_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
        conn.execute(
            "INSERT INTO app_state VALUES(1,?,CURRENT_TIMESTAMP)",
            (json.dumps({"schemaVersion": 1, "expenses": [], "incomeRecords": []}),),
        )
        conn.commit()

    candidate = tmp_path / ".migration-candidate.db"
    candidate_wal = Path(str(candidate) + "-wal")
    candidate_shm = Path(str(candidate) + "-shm")
    candidate_wal.write_bytes(b"stale-wal")
    candidate_shm.write_bytes(b"stale-shm")
    real_connect = sqlite3.connect

    def guarded_connect(database, *args, **kwargs):
        if Path(str(database)) == candidate:
            assert not candidate_wal.exists()
            assert not candidate_shm.exists()
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(database_module.sqlite3, "connect", guarded_connect)
    Database(path)
