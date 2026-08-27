from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List

from .money import yuan_to_cents
from .storage_v6 import _json_extra, _uid


SUPPORTED_KEYS = {
    "settings",
    "saleCategories",
    "expenseCategories",
    "products",
    "incomeRecords",
    "expenses",
}


def _by_id(rows: Iterable[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        row_id = int(row.get("id") or index + 1)
        result[row_id] = row
    return result


def _changed_ids(before: Iterable[Dict[str, Any]], after: Iterable[Dict[str, Any]]) -> tuple[set[int], set[int]]:
    old = _by_id(before)
    new = _by_id(after)
    changed = {row_id for row_id, row in new.items() if old.get(row_id) != row}
    deleted = set(old) - set(new)
    return changed, deleted


def _sync_settings(conn, before: Dict[str, Any], after: Dict[str, Any]) -> None:
    if before == after:
        return
    now = datetime.now().isoformat(timespec="seconds")
    password_hash = after.get("passwordHash")
    normal = {key: value for key, value in after.items() if key != "passwordHash"}
    old_normal = {key: value for key, value in before.items() if key != "passwordHash"}
    for key in set(old_normal) - set(normal):
        conn.execute("DELETE FROM settings_v6 WHERE key=?", (key,))
    for key, value in normal.items():
        if old_normal.get(key) == value and key in old_normal:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO settings_v6(key,value,value_type,updated_at) VALUES(?,?,?,?)",
            (str(key), json.dumps(value, ensure_ascii=False), "json", now),
        )
    conn.execute(
        "INSERT OR REPLACE INTO security_settings(id,password_hash,recovery_hash,password_changed_at,updated_at) VALUES(1,?,COALESCE((SELECT recovery_hash FROM security_settings WHERE id=1),NULL),?,?)",
        (password_hash, now if password_hash != before.get("passwordHash") else None, now),
    )


def _sync_categories(conn, table: str, before: List[Dict[str, Any]], after: List[Dict[str, Any]], entity: str) -> None:
    if before == after:
        return
    old_ids = set(_by_id(before))
    new_ids = set(_by_id(after))
    for row_id in old_ids - new_ids:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
    for index, row in enumerate(after):
        row_id = int(row.get("id") or index + 1)
        if row_id in old_ids and _by_id(before).get(row_id) == row:
            continue
        conn.execute(
            f"INSERT OR REPLACE INTO {table}(id,uid,name,active,sort_order,legacy_json) VALUES(?,?,?,?,?,?)",
            (row_id, _uid(entity, row_id, str(index)), str(row.get("name", "")), int(bool(row.get("active", True))), index, _json_extra(row, ("id", "name", "active"))),
        )


def _sync_products(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM products_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute(
            """INSERT OR REPLACE INTO products_v6(id,uid,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("product", row_id, str(row_id)), str(row.get("name", "")), str(row.get("category", "")),
                str(row.get("brand", "")), str(row.get("spec", "")), str(row.get("unit", "")), int(bool(row.get("stocktake", False))),
                int(bool(row.get("reminder", False))), int(bool(row.get("active", True))), row.get("createdAt"),
                _json_extra(row, ("id", "name", "category", "brand", "spec", "unit", "stocktake", "reminder", "active", "createdAt")),
            ),
        )


def _sync_income(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM income_records_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        hall = row.get("hall")
        room = row.get("room")
        dine_in = row.get("dineIn", float(hall or 0) + float(room or 0))
        date_value = str(row.get("date", ""))
        conn.execute(
            """INSERT OR REPLACE INTO income_records_v6(id,uid,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("income", row_id, str(row_id)), date_value, str(row.get("entryMode", "day")), str(row.get("periodStart") or date_value),
                str(row.get("periodEnd") or date_value), yuan_to_cents(dine_in), None if hall is None else yuan_to_cents(hall), None if room is None else yuan_to_cents(room),
                yuan_to_cents(row.get("chess", 0)), yuan_to_cents(row.get("delivery", 0)), str(row.get("note", "")),
                _json_extra(row, ("id", "date", "entryMode", "periodStart", "periodEnd", "dineIn", "hall", "room", "chess", "delivery", "note")),
            ),
        )


def _sync_expenses(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM expenses_v6 WHERE id=?", (row_id,))
    categories = {str(name): int(row_id) for row_id, name in conn.execute("SELECT id,name FROM expense_categories_v6")}
    products = {int(row_id): str(name) for row_id, name in conn.execute("SELECT id,name FROM products_v6")}
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        category = str(row.get("category", ""))
        product_id = row.get("productId")
        price = row.get("price")
        conn.execute(
            """INSERT OR REPLACE INTO expenses_v6(id,uid,expense_date,mode,category_id,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,product_name_snapshot,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("expense", row_id, str(row_id)), str(row.get("date", "")), str(row.get("mode", "")), categories.get(category), category,
                str(row.get("item", "")), yuan_to_cents(row.get("amount", 0)), str(row.get("handler", "")), str(row.get("status", "有效")), str(row.get("note", "")),
                row.get("purchaseNo"), product_id, products.get(int(product_id)) if product_id not in (None, "") else None, row.get("qty"), row.get("unit"),
                None if price is None else yuan_to_cents(price), row.get("importBatchId"),
                _json_extra(row, ("id", "date", "mode", "category", "item", "amount", "handler", "status", "note", "purchaseNo", "productId", "qty", "unit", "price", "importBatchId")),
            ),
        )


def sync_legacy_changes(conn, before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    """Incrementally mirror converted legacy groups into relational tables.

    Returns changed top-level groups that do not yet have an incremental synchronizer.
    """
    _sync_settings(conn, dict(before.get("settings", {})), dict(after.get("settings", {})))
    _sync_categories(conn, "sale_categories_v6", list(before.get("saleCategories", [])), list(after.get("saleCategories", [])), "sale-category")
    _sync_categories(conn, "expense_categories_v6", list(before.get("expenseCategories", [])), list(after.get("expenseCategories", [])), "expense-category")
    _sync_products(conn, list(before.get("products", [])), list(after.get("products", [])))
    _sync_income(conn, list(before.get("incomeRecords", [])), list(after.get("incomeRecords", [])))
    _sync_expenses(conn, list(before.get("expenses", [])), list(after.get("expenses", [])))

    ignored = {"schemaVersion"}
    keys = set(before) | set(after)
    return sorted(key for key in keys if key not in SUPPORTED_KEYS and key not in ignored and before.get(key) != after.get(key))
