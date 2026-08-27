from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from .money import yuan_to_cents
from .storage_v6 import _json_extra, _uid


EXTENDED_KEYS = {
    "salesRecords",
    "stocktakes",
    "employees",
    "payrolls",
    "suppliers",
    "reminders",
    "assets",
    "importBatches",
}


def _by_id(rows: Iterable[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        result[int(row.get("id") or index + 1)] = row
    return result


def _changed_ids(before: Iterable[Dict[str, Any]], after: Iterable[Dict[str, Any]]) -> tuple[set[int], set[int]]:
    old = _by_id(before)
    new = _by_id(after)
    return ({row_id for row_id, row in new.items() if old.get(row_id) != row}, set(old) - set(new))


def _sync_sales(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM sales_records_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute("DELETE FROM sales_records_v6 WHERE id=?", (row_id,))
        conn.execute(
            "INSERT INTO sales_records_v6(id,uid,sale_date,legacy_json) VALUES(?,?,?,?)",
            (row_id, _uid("sales", row_id, str(row_id)), str(row.get("date", "")), _json_extra(row, ("id", "date", "rows"))),
        )
        for line in row.get("rows", []):
            conn.execute(
                "INSERT INTO sales_lines_v6(sales_record_id,category_id,category_name_snapshot,quantity,amount_cents,legacy_json) VALUES(?,?,?,?,?,?)",
                (
                    row_id, line.get("categoryId"), str(line.get("category", "")), float(line.get("qty", 0) or 0), yuan_to_cents(line.get("amount", 0)),
                    _json_extra(line, ("categoryId", "category", "qty", "amount")),
                ),
            )


def _sync_stocktakes(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM stocktakes_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute("DELETE FROM stocktakes_v6 WHERE id=?", (row_id,))
        conn.execute(
            "INSERT INTO stocktakes_v6(id,uid,stocktake_date,kind,legacy_json) VALUES(?,?,?,?,?)",
            (row_id, _uid("stocktake", row_id, str(row_id)), str(row.get("date", "")), str(row.get("kind", "")), _json_extra(row, ("id", "date", "kind", "rows"))),
        )
        for line in row.get("rows", []):
            conn.execute(
                """INSERT INTO stocktake_lines_v6(stocktake_id,product_id,product_name_snapshot,unit_snapshot,previous_quantity,actual_quantity,change_quantity,note,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    row_id, line.get("productId"), str(line.get("product", "")), str(line.get("unit", "")), float(line.get("previous", 0) or 0),
                    float(line.get("actual", 0) or 0), float(line.get("change", 0) or 0), str(line.get("note", "")),
                    _json_extra(line, ("productId", "product", "unit", "previous", "actual", "change", "note")),
                ),
            )


def _sync_employees(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM employees_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute(
            """INSERT OR REPLACE INTO employees_v6(id,uid,name,role,standard_salary_cents,start_date,active,legacy_json)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("employee", row_id, str(row_id)), str(row.get("name", "")), str(row.get("role", "")), yuan_to_cents(row.get("salary", 0)),
                str(row.get("startDate", "")), int(bool(row.get("active", True))), _json_extra(row, ("id", "name", "role", "salary", "startDate", "active")),
            ),
        )


def _payroll_map(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row.get("month", "")): row for row in rows if str(row.get("month", ""))}


def _sync_payrolls(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    old = _payroll_map(before)
    new = _payroll_map(after)
    for month in set(old) - set(new):
        conn.execute("DELETE FROM payrolls_v6 WHERE month=?", (month,))
    for month, row in new.items():
        if old.get(month) == row:
            continue
        conn.execute("DELETE FROM payrolls_v6 WHERE month=?", (month,))
        cursor = conn.execute(
            "INSERT INTO payrolls_v6(uid,month,confirmed,legacy_json) VALUES(?,?,?,?)",
            (_uid("payroll", month, month), month, int(bool(row.get("confirmed", False))), _json_extra(row, ("month", "confirmed", "rows"))),
        )
        payroll_id = int(cursor.lastrowid)
        for line in row.get("rows", []):
            conn.execute(
                """INSERT INTO payroll_lines_v6(payroll_id,employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    payroll_id, line.get("employeeId"), str(line.get("name", "")), str(line.get("role", "")), yuan_to_cents(line.get("standard", 0)),
                    yuan_to_cents(line.get("amount", 0)), str(line.get("note", "")), _json_extra(line, ("employeeId", "name", "role", "standard", "amount", "note")),
                ),
            )


def _sync_suppliers(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM suppliers_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute(
            """INSERT OR REPLACE INTO suppliers_v6(id,uid,name,contact,phone,qualification,note,active,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("supplier", row_id, str(row_id)), str(row.get("name", "")), str(row.get("contact", "")), str(row.get("phone", "")),
                str(row.get("qualification", "")), str(row.get("note", "")), int(bool(row.get("active", True))),
                _json_extra(row, ("id", "name", "contact", "phone", "qualification", "note", "active")),
            ),
        )


def _sync_reminders(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM reminders_v6 WHERE id=?", (row_id,))
    product_ids = {str(name): int(product_id) for product_id, name in conn.execute("SELECT id,name FROM products_v6")}
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        product = str(row.get("product", ""))
        conn.execute(
            """INSERT OR REPLACE INTO reminders_v6(id,uid,name,product_id,product_name_snapshot,next_date,cycle_days,done,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("reminder", row_id, str(row_id)), str(row.get("name", "")), product_ids.get(product), product, str(row.get("date", "")),
                int(row.get("cycle", 0) or 0), int(bool(row.get("done", False))), _json_extra(row, ("id", "name", "product", "date", "cycle", "done")),
            ),
        )


def _sync_assets(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    changed, deleted = _changed_ids(before, after)
    for row_id in deleted:
        conn.execute("DELETE FROM assets_v6 WHERE id=?", (row_id,))
    rows = _by_id(after)
    for row_id in changed:
        row = rows[row_id]
        conn.execute(
            """INSERT OR REPLACE INTO assets_v6(id,uid,asset_type,name,quantity,unit,record_date,amount_cents,status,note,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row_id, _uid("asset", row_id, str(row_id)), str(row.get("type", "asset")), str(row.get("name", "")), float(row.get("qty", 0) or 0),
                str(row.get("unit", "")), str(row.get("date", "")), yuan_to_cents(row.get("amount", 0)), str(row.get("status", "")), str(row.get("note", "")),
                _json_extra(row, ("id", "type", "name", "qty", "unit", "date", "amount", "status", "note")),
            ),
        )


def _batch_map(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row.get("id", "")): row for row in rows if str(row.get("id", ""))}


def _sync_import_batches(conn, before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> None:
    old = _batch_map(before)
    new = _batch_map(after)
    for batch_id in set(old) - set(new):
        conn.execute("DELETE FROM import_batches_v6 WHERE id=?", (batch_id,))
    for batch_id, row in new.items():
        if old.get(batch_id) == row:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO import_batches_v6(id,file_name,imported_at,payload_json) VALUES(?,?,?,?)",
            (batch_id, str(row.get("file", "")), str(row.get("importedAt", "")), json.dumps(row, ensure_ascii=False, separators=(",", ":"))),
        )


def sync_extended_legacy_changes(conn, before: Dict[str, Any], after: Dict[str, Any]) -> None:
    _sync_sales(conn, list(before.get("salesRecords", [])), list(after.get("salesRecords", [])))
    _sync_stocktakes(conn, list(before.get("stocktakes", [])), list(after.get("stocktakes", [])))
    _sync_employees(conn, list(before.get("employees", [])), list(after.get("employees", [])))
    _sync_payrolls(conn, list(before.get("payrolls", [])), list(after.get("payrolls", [])))
    _sync_suppliers(conn, list(before.get("suppliers", [])), list(after.get("suppliers", [])))
    _sync_reminders(conn, list(before.get("reminders", [])), list(after.get("reminders", [])))
    _sync_assets(conn, list(before.get("assets", [])), list(after.get("assets", [])))
    _sync_import_batches(conn, list(before.get("importBatches", [])), list(after.get("importBatches", [])))
