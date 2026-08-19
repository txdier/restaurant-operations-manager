from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Dict

from .version import DATA_SCHEMA_VERSION


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
            "lastAutoBackupDate": "",
            "createdAt": today,
        },
    }


def migrate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    base = default_state()
    for key, value in base.items():
        state.setdefault(key, value)
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
    state["schemaVersion"] = DATA_SCHEMA_VERSION
    return state


def migrate_database(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if row is None:
            conn.execute("INSERT INTO app_state(id,payload) VALUES(1,?)", (json.dumps(default_state(), ensure_ascii=False),))
        else:
            state = migrate_state(json.loads(row[0]))
            conn.execute("UPDATE app_state SET payload=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False),))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(DATA_SCHEMA_VERSION),))
