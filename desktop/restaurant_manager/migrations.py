from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any, Dict

from .storage_v6 import RELATIONAL_SCHEMA_VERSION, relational_state_available, state_to_v6, validate_v6
from .version import DATA_SCHEMA_MIN_APP_VERSION, DATA_SCHEMA_VERSION


def default_state() -> Dict[str, Any]:
    today = date.today().isoformat()
    categories = ["主食", "小炒菜", "酒水", "烧菜类", "招牌菜", "汤类", "干锅类", "时蔬", "凉菜", "棋牌"]
    expense_categories = ["食材", "酒水", "耗材", "水电燃气", "装修", "设备置物", "人工工资", "其他"]
    employees = [
        {"id": 1, "name": "张师傅", "role": "厨师", "salary": 6000, "startDate": "2024-03-01", "active": True},
        {"id": 2, "name": "李服务", "role": "服务员", "salary": 4000, "startDate": "2025-06-12", "active": True},
        {"id": 3, "name": "王阿姨", "role": "保洁", "salary": 2800, "startDate": "2025-11-08", "active": True},
    ]
    return {
        "schemaVersion": DATA_SCHEMA_VERSION,
        "incomeRecords": [],
        "salesRecords": [],
        "expenses": [],
        "products": [],
        "stocktakes": [],
        "reminders": [],
        "saleCategories": [{"id": i + 1, "name": name, "active": True} for i, name in enumerate(categories)],
        "expenseCategories": [{"id": i + 1, "name": name, "active": True} for i, name in enumerate(expense_categories)],
        "importBatches": [],
        "employees": employees,
        "payrolls": [],
        "suppliers": [],
        "assets": [],
        "settings": {
            "storeName": "我的餐馆",
            "owner": "老板",
            "backupDir": "",
            "backupTime": "08:00",
            "backupKeepDays": 30,
            "autoLockMinutes": 15,
            "appName": "餐馆经营管理系统",
            "windowTitle": "餐馆经营管理系统",
            "logoDataUrl": "",
            "desktopShortcutName": "餐馆经营管理系统",
            "desktopIconDataUrl": "",
            "autoCheckUpdates": True,
            "lastUpdateCheckAt": "",
            "latestKnownVersion": "",
            "latestReleaseUrl": "",
            "lastAutoBackupDate": "",
            "createdAt": today,
        },
    }


def migrate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    base = default_state()
    for key, value in base.items():
        state.setdefault(key, value)
    settings = state.setdefault("settings", {})
    for key, value in base["settings"].items():
        settings.setdefault(key, value)
    version = int(state.get("schemaVersion", 1))
    if version < 2:
        if "income" in state and not state.get("incomeRecords"):
            old = state.pop("income")
            state["incomeRecords"] = [{"id": 1, **old}]
        if "payroll" in state and not state.get("payrolls"):
            old_payroll = state.pop("payroll")
            state["payrolls"] = [old_payroll]
        version = 2
    if version < 3:
        for product in state.get("products", []):
            product.setdefault("createdAt", date.today().isoformat())
        for expense in state.get("expenses", []):
            expense.setdefault("lines", [])
        version = 3
    if version < 4:
        state.setdefault("expenseCategories", base["expenseCategories"])
        state.setdefault("importBatches", [])
        version = 4
    if version < 5:
        used_ids = {int(income["id"]) for income in state.get("incomeRecords", []) if income.get("id") is not None}
        next_id = max(used_ids, default=0) + 1
        for income in state.get("incomeRecords", []):
            if income.get("id") is None:
                while next_id in used_ids:
                    next_id += 1
                income["id"] = next_id
                used_ids.add(next_id)
                next_id += 1
            income.setdefault("entryMode", "day")
            income.setdefault("periodStart", income.get("date", ""))
            income.setdefault("periodEnd", income.get("date", ""))
            income.setdefault("dineIn", float(income.get("hall", 0) or 0) + float(income.get("room", 0) or 0))
        version = 5
    state["schemaVersion"] = DATA_SCHEMA_VERSION
    return state


def migrate_database(conn: sqlite3.Connection) -> None:
    removed_app_state = False
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        if DATA_SCHEMA_VERSION >= RELATIONAL_SCHEMA_VERSION and not relational_state_available(conn):
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            legacy = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone() if "app_state" in tables else None
            state = migrate_state(json.loads(legacy[0])) if legacy else default_state()
            state_to_v6(conn, state)
            checks = validate_v6(conn, state)
            conn.execute(
                "INSERT OR REPLACE INTO schema_migrations(version,applied_at,detail) VALUES(?,?,?)",
                (RELATIONAL_SCHEMA_VERSION, datetime.now().isoformat(timespec="seconds"), json.dumps(checks, ensure_ascii=False, separators=(",", ":"))),
            )
        if DATA_SCHEMA_VERSION >= 7:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            foreign_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if not integrity or integrity[0] != "ok" or foreign_errors:
                raise ValueError("删除旧状态前的关系数据库完整性检查失败")
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            removed_app_state = "app_state" in tables
            conn.execute("DROP TABLE IF EXISTS app_state")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at,detail) VALUES(?,?,?)",
                (7, datetime.now().isoformat(timespec="seconds"), json.dumps({"integrity": "ok", "foreignKeyErrors": 0, "appStateRemoved": removed_app_state}, separators=(",", ":"))),
            )
            conn.execute("DELETE FROM meta WHERE key='relational_snapshot_dirty'")
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(DATA_SCHEMA_VERSION),))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('min_app_version',?)", (DATA_SCHEMA_MIN_APP_VERSION,))
    if removed_app_state:
        conn.execute("VACUUM")
