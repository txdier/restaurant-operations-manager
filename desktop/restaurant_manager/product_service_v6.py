from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from .repositories_v6 import V6Repository
from .storage_v6 import _uid


def product_has_history_v6(database: Any, product_id: int) -> bool:
    with database.lock, database.connect() as conn:
        expense = conn.execute("SELECT 1 FROM expenses_v6 WHERE product_id=? LIMIT 1", (int(product_id),)).fetchone()
        stocktake = conn.execute("SELECT 1 FROM stocktake_lines_v6 WHERE product_id=? LIMIT 1", (int(product_id),)).fetchone()
        return bool(expense or stocktake)


def set_product_active_v6(database: Any, product_id: int, active: bool) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json FROM products_v6 WHERE id=?",
            (int(product_id),),
        ).fetchone()
        if not row:
            raise ValueError("商品不存在")
        reminder_enabled = bool(row[7]) if active else False
        conn.execute("UPDATE products_v6 SET active=?,reminder_enabled=? WHERE id=?", (int(bool(active)), int(reminder_enabled), int(product_id)))
        if not active:
            conn.execute("UPDATE reminders_v6 SET done=1 WHERE product_id=? AND done=0", (int(product_id),))

        state_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if not state_row:
            raise RuntimeError("本地数据库缺少兼容状态")
        state = json.loads(state_row[0])
        for product in state.get("products", []):
            if int(product.get("id", 0)) == int(product_id):
                product["active"] = bool(active)
                if not active:
                    product["reminder"] = False
                break
        if not active:
            name = str(row[1])
            for reminder in state.get("reminders", []):
                if str(reminder.get("product", "")) == name and not reminder.get("done", False):
                    reminder["done"] = True
        conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", ("product.active", json.dumps({"id": int(product_id), "active": bool(active)}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
    return V6Repository(database).list_products(query="", active=None, limit=2000)[0] if False else V6Repository(database).upsert_product({
        "id": int(product_id), "name": str(row[1]), "category": str(row[2]), "brand": str(row[3]), "spec": str(row[4]), "unit": str(row[5]),
        "stocktake": bool(row[6]), "reminder": reminder_enabled, "active": bool(active), "createdAt": row[9],
    })


def replace_product_unit_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    product_id = int(payload.get("id") or 0)
    new_unit = str(payload.get("unit", "")).strip()
    if not product_id or not new_unit:
        raise ValueError("商品和新单位不能为空")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at FROM products_v6 WHERE id=?",
            (product_id,),
        ).fetchone()
        if not row:
            raise ValueError("商品不存在")
        old_unit = str(row[5])
        if old_unit == new_unit:
            raise ValueError("新单位与原单位相同")
        if not product_has_history_v6(database, product_id):
            raise ValueError("该商品没有历史记录，请直接编辑单位")

        new_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM products_v6").fetchone()[0])
        name = str(payload.get("name") or row[1]).strip()
        category = str(payload.get("category") or row[2])
        brand = str(payload.get("brand") if payload.get("brand") is not None else row[3])
        spec = str(payload.get("spec") if payload.get("spec") is not None else row[4])
        stocktake = bool(payload.get("stocktake", row[6]))
        reminder = bool(payload.get("reminder", row[7]))
        created_at = datetime.now().date().isoformat()
        conn.execute("UPDATE products_v6 SET active=0,reminder_enabled=0 WHERE id=?", (product_id,))
        conn.execute("UPDATE reminders_v6 SET done=1 WHERE product_id=? AND done=0", (product_id,))
        conn.execute(
            """INSERT INTO products_v6(id,uid,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (new_id, _uid("product", new_id, str(new_id)), name, category, brand, spec, new_unit, int(stocktake), int(reminder), 1, created_at, ""),
        )

        state_row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
        if not state_row:
            raise RuntimeError("本地数据库缺少兼容状态")
        state = json.loads(state_row[0])
        old_name = str(row[1])
        for product in state.get("products", []):
            if int(product.get("id", 0)) == product_id:
                product["active"] = False
                product["reminder"] = False
                break
        replacement = {"id": new_id, "name": name, "category": category, "brand": brand, "spec": spec, "unit": new_unit, "stocktake": stocktake, "reminder": reminder, "active": True, "createdAt": created_at}
        state.setdefault("products", []).append(replacement)
        for reminder_row in state.get("reminders", []):
            if str(reminder_row.get("product", "")) == old_name and not reminder_row.get("done", False):
                reminder_row["done"] = True
        conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", ("product.replace_unit", json.dumps({"oldId": product_id, "newId": new_id, "oldUnit": old_unit, "newUnit": new_unit}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
        return {"oldId": product_id, "newProduct": replacement}
