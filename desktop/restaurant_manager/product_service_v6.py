from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from .storage_v6 import _uid


def _has_history(conn, product_id: int) -> bool:
    expense = conn.execute("SELECT 1 FROM expenses_v6 WHERE product_id=? LIMIT 1", (int(product_id),)).fetchone()
    stocktake = conn.execute("SELECT 1 FROM stocktake_lines_v6 WHERE product_id=? LIMIT 1", (int(product_id),)).fetchone()
    return bool(expense or stocktake)


def product_has_history_v6(database: Any, product_id: int) -> bool:
    with database.lock, database.connect() as conn:
        return _has_history(conn, int(product_id))


def set_product_active_v6(database: Any, product_id: int, active: bool) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at FROM products_v6 WHERE id=?",
            (int(product_id),),
        ).fetchone()
        if not row:
            raise ValueError("商品不存在")
        reminder_enabled = bool(row[7]) if active else False
        conn.execute("UPDATE products_v6 SET active=?,reminder_enabled=? WHERE id=?", (int(bool(active)), int(reminder_enabled), int(product_id)))
        if not active:
            conn.execute("UPDATE reminders_v6 SET done=1 WHERE product_id=? AND done=0", (int(product_id),))

        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", ("product.active", json.dumps({"id": int(product_id), "active": bool(active)}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
        return {
            "id": int(row[0]), "name": str(row[1]), "category": str(row[2]), "brand": str(row[3]), "spec": str(row[4]),
            "unit": str(row[5]), "stocktake": bool(row[6]), "reminder": reminder_enabled, "active": bool(active), "createdAt": row[9],
        }


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
        if not _has_history(conn, product_id):
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

        replacement = {"id": new_id, "name": name, "category": category, "brand": brand, "spec": spec, "unit": new_unit, "stocktake": stocktake, "reminder": reminder, "active": True, "createdAt": created_at}
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", ("product.replace_unit", json.dumps({"oldId": product_id, "newId": new_id, "oldUnit": old_unit, "newUnit": new_unit}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
        return {"oldId": product_id, "newProduct": replacement}
