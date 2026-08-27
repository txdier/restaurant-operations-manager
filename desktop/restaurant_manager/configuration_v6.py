from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from .security import hash_password, verify_password
from .storage_v6 import _uid


def load_settings_v6(database: Any, include_password: bool = False) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        settings: Dict[str, Any] = {}
        for key, value in conn.execute("SELECT key,value FROM settings_v6 ORDER BY key"):
            settings[str(key)] = json.loads(value)
        if include_password:
            row = conn.execute("SELECT password_hash FROM security_settings WHERE id=1").fetchone()
            if row and row[0]:
                settings["passwordHash"] = str(row[0])
        return settings


def security_status_v6(database: Any) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        row = conn.execute("SELECT password_hash,recovery_hash,password_changed_at FROM security_settings WHERE id=1").fetchone()
    return {
        "hasPassword": bool(row and row[0]),
        "hasRecoveryCode": bool(row and row[1]),
        "passwordChangedAt": str(row[2]) if row and row[2] else "",
    }


def bootstrap_v6(database: Any) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        settings = {str(key): json.loads(value) for key, value in conn.execute("SELECT key,value FROM settings_v6 ORDER BY key")}
        sale_categories = [
            {"id": int(row[0]), "name": str(row[1]), "active": bool(row[2])}
            for row in conn.execute("SELECT id,name,active FROM sale_categories_v6 ORDER BY sort_order,id")
        ]
        expense_categories = [
            {"id": int(row[0]), "name": str(row[1]), "active": bool(row[2])}
            for row in conn.execute("SELECT id,name,active FROM expense_categories_v6 ORDER BY sort_order,id")
        ]
        security = conn.execute("SELECT password_hash,recovery_hash,password_changed_at FROM security_settings WHERE id=1").fetchone()
    return {
        "settings": settings,
        "saleCategories": sale_categories,
        "expenseCategories": expense_categories,
        "security": {
            "hasPassword": bool(security and security[0]),
            "hasRecoveryCode": bool(security and security[1]),
            "passwordChangedAt": str(security[2]) if security and security[2] else "",
        },
    }


def patch_settings_v6(database: Any, patch: Dict[str, Any], event: str = "settings.patch") -> Dict[str, Any]:
    clean = {str(key): value for key, value in patch.items() if key not in ("passwordHash", "recoveryHash")}
    if not clean:
        return load_settings_v6(database)
    now = datetime.now().isoformat(timespec="seconds")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if not state_row:
            raise RuntimeError("本地数据库缺少兼容状态")
        state = json.loads(state_row[0])
        legacy_settings = state.setdefault("settings", {})
        for key, value in clean.items():
            conn.execute(
                "INSERT OR REPLACE INTO settings_v6(key,value,value_type,updated_at) VALUES(?,?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), "json", now),
            )
            legacy_settings[key] = value
        conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", (event, json.dumps({"keys": sorted(clean)}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
    return load_settings_v6(database)


def _save_categories(database: Any, table: str, state_key: str, entity: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names = [str(row.get("name", "")).strip() for row in rows]
    if not rows or any(not name for name in names):
        raise ValueError("分类名称不能为空")
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("分类名称不能重复")
    if not any(bool(row.get("active", True)) for row in rows):
        raise ValueError("请至少保留一个启用分类")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_ids = {int(row[0]) for row in conn.execute(f"SELECT id FROM {table}")}
        next_id = max(existing_ids or {0}) + 1
        saved: List[Dict[str, Any]] = []
        incoming_ids = set()
        for sort_order, row in enumerate(rows):
            row_id = int(row.get("id") or 0)
            if not row_id or row_id not in existing_ids:
                row_id = next_id
                next_id += 1
            incoming_ids.add(row_id)
            item = {"id": row_id, "name": str(row.get("name", "")).strip(), "active": bool(row.get("active", True))}
            conn.execute(
                f"INSERT OR REPLACE INTO {table}(id,uid,name,active,sort_order,legacy_json) VALUES(?,?,?,?,?,?)",
                (row_id, _uid(entity, row_id, str(row_id)), item["name"], int(item["active"]), sort_order, ""),
            )
            saved.append(item)
        for missing_id in existing_ids - incoming_ids:
            conn.execute(f"UPDATE {table} SET active=0 WHERE id=?", (missing_id,))
        state_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if not state_row:
            raise RuntimeError("本地数据库缺少兼容状态")
        state = json.loads(state_row[0])
        state[state_key] = saved
        conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", (f"{state_key}.save", json.dumps({"count": len(saved)}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
        return saved


def save_sale_categories_v6(database: Any, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _save_categories(database, "sale_categories_v6", "saleCategories", "sale-category", rows)


def save_expense_categories_v6(database: Any, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _save_categories(database, "expense_categories_v6", "expenseCategories", "expense-category", rows)


def change_password_v6(database: Any, current: str, new: str) -> None:
    encoded_new = hash_password(new)
    now = datetime.now().isoformat(timespec="seconds")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT password_hash,recovery_hash FROM security_settings WHERE id=1").fetchone()
        encoded = str(row[0]) if row and row[0] else ""
        if encoded and not verify_password(current, encoded):
            raise ValueError("当前密码不正确")
        recovery = row[1] if row else None
        conn.execute(
            "INSERT OR REPLACE INTO security_settings(id,password_hash,recovery_hash,password_changed_at,updated_at) VALUES(1,?,?,?,?,?)",
            (encoded_new, recovery, now, now),
        )
        state_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if not state_row:
            raise RuntimeError("本地数据库缺少兼容状态")
        state = json.loads(state_row[0])
        state.setdefault("settings", {})["passwordHash"] = encoded_new
        conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
        conn.execute("INSERT INTO audit_log(event,detail) VALUES('change_password','{}')")
        conn.commit()


def verify_unlock_v6(database: Any, password: str) -> bool:
    with database.lock, database.connect() as conn:
        row = conn.execute("SELECT password_hash FROM security_settings WHERE id=1").fetchone()
    encoded = str(row[0]) if row and row[0] else ""
    return not encoded or verify_password(password, encoded)
