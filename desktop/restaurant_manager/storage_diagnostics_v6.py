from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .storage_v6 import RELATIONAL_SCHEMA_VERSION, relational_state_available


COUNT_TABLES = (
    "income_records_v6",
    "sales_records_v6",
    "sales_lines_v6",
    "expenses_v6",
    "products_v6",
    "stocktakes_v6",
    "stocktake_lines_v6",
    "employees_v6",
    "payrolls_v6",
    "payroll_lines_v6",
    "suppliers_v6",
    "reminders_v6",
    "assets_v6",
    "import_batches_v6",
)


def storage_status(database: Any, verify: bool = False) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        available = relational_state_available(conn)
        schema_row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        min_app_row = conn.execute("SELECT value FROM meta WHERE key='min_app_version'").fetchone()
        dirty_row = conn.execute("SELECT value FROM meta WHERE key='relational_snapshot_dirty'").fetchone()
        app_state_row = conn.execute("SELECT LENGTH(payload) FROM app_state WHERE id=1").fetchone()
        migration = conn.execute("SELECT applied_at,detail FROM schema_migrations WHERE version=?", (RELATIONAL_SCHEMA_VERSION,)).fetchone() if available else None
        counts: Dict[str, int] = {}
        if available:
            for table in COUNT_TABLES:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        result: Dict[str, Any] = {
            "schemaVersion": int(schema_row[0]) if schema_row else 0,
            "relationalVersion": RELATIONAL_SCHEMA_VERSION if available else 0,
            "relationalAvailable": available,
            "relationalDirty": bool(dirty_row and dirty_row[0] == "1"),
            "minAppVersion": str(min_app_row[0]) if min_app_row else "",
            "databaseSize": Path(database.path).stat().st_size if Path(database.path).exists() else 0,
            "legacyMirrorBytes": int(app_state_row[0] or 0) if app_state_row else 0,
            "counts": counts,
            "migrationAppliedAt": str(migration[0]) if migration else "",
        }
        if verify:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
            result["integrity"] = integrity[0] if integrity else "missing"
            result["foreignKeyErrors"] = len(foreign)
            result["verified"] = result["integrity"] == "ok" and not foreign
        return result
