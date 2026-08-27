from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable
from uuid import NAMESPACE_URL, uuid5

from .money import cents_to_legacy_number, yuan_to_cents


RELATIONAL_SCHEMA_VERSION = 6


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _uid(entity: str, legacy_id: Any, fallback: str) -> str:
    source = f"restaurant-manager:{entity}:{legacy_id if legacy_id not in (None, '') else fallback}"
    return str(uuid5(NAMESPACE_URL, source))


def _json_extra(row: Dict[str, Any], known: Iterable[str]) -> str:
    extra = {key: value for key, value in row.items() if key not in set(known)}
    return json.dumps(extra, ensure_ascii=False, separators=(",", ":")) if extra else ""


def create_schema_v6(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS settings_v6 (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'json',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS security_settings (
            id INTEGER PRIMARY KEY CHECK(id=1),
            password_hash TEXT,
            recovery_hash TEXT,
            password_changed_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sale_categories_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            active INTEGER NOT NULL,
            sort_order INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS expense_categories_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            active INTEGER NOT NULL,
            sort_order INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS products_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category_name_snapshot TEXT NOT NULL,
            brand TEXT NOT NULL DEFAULT '',
            spec TEXT NOT NULL DEFAULT '',
            unit TEXT NOT NULL,
            stocktake_enabled INTEGER NOT NULL,
            reminder_enabled INTEGER NOT NULL,
            active INTEGER NOT NULL,
            created_at TEXT,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS income_records_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            record_date TEXT NOT NULL,
            entry_mode TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            dine_in_cents INTEGER NOT NULL,
            hall_cents INTEGER,
            room_cents INTEGER,
            chess_cents INTEGER NOT NULL,
            delivery_cents INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sales_records_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            sale_date TEXT NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sales_lines_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_record_id INTEGER NOT NULL,
            category_id INTEGER,
            category_name_snapshot TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            amount_cents INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(sales_record_id) REFERENCES sales_records_v6(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS expenses_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            expense_date TEXT NOT NULL,
            mode TEXT NOT NULL,
            category_id INTEGER,
            category_name_snapshot TEXT NOT NULL,
            item TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            handler TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            purchase_no TEXT,
            product_id INTEGER,
            product_name_snapshot TEXT,
            quantity REAL,
            unit_snapshot TEXT,
            unit_price_cents INTEGER,
            import_batch_id TEXT,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS stocktakes_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            stocktake_date TEXT NOT NULL,
            kind TEXT NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS stocktake_lines_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stocktake_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name_snapshot TEXT NOT NULL,
            unit_snapshot TEXT NOT NULL,
            previous_quantity REAL NOT NULL DEFAULT 0,
            actual_quantity REAL NOT NULL DEFAULT 0,
            change_quantity REAL NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            legacy_json TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(stocktake_id) REFERENCES stocktakes_v6(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS employees_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            standard_salary_cents INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            active INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS payrolls_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL UNIQUE,
            month TEXT NOT NULL UNIQUE,
            confirmed INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS payroll_lines_v6 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_id INTEGER NOT NULL,
            employee_id INTEGER,
            employee_name_snapshot TEXT NOT NULL,
            role_snapshot TEXT NOT NULL,
            standard_salary_cents INTEGER NOT NULL,
            actual_salary_cents INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            legacy_json TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(payroll_id) REFERENCES payrolls_v6(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS suppliers_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            contact TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            qualification TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS reminders_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            product_id INTEGER,
            product_name_snapshot TEXT NOT NULL,
            next_date TEXT NOT NULL,
            cycle_days INTEGER NOT NULL,
            done INTEGER NOT NULL,
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS assets_v6 (
            id INTEGER PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            asset_type TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            record_date TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            legacy_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS import_batches_v6 (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_v6_date ON expenses_v6(expense_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_status_date ON expenses_v6(status, expense_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_category_date ON expenses_v6(category_id, expense_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_handler_date ON expenses_v6(handler, expense_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_product_date ON expenses_v6(product_id, expense_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_purchase_no ON expenses_v6(purchase_no);
        CREATE INDEX IF NOT EXISTS idx_expenses_v6_amount ON expenses_v6(amount_cents);
        CREATE INDEX IF NOT EXISTS idx_income_v6_date ON income_records_v6(record_date);
        CREATE INDEX IF NOT EXISTS idx_sales_v6_date ON sales_records_v6(sale_date);
        CREATE INDEX IF NOT EXISTS idx_stocktakes_v6_date ON stocktakes_v6(stocktake_date);
        CREATE INDEX IF NOT EXISTS idx_reminders_v6_status_date ON reminders_v6(done, next_date);
        """
    )


def clear_v6_data(conn: sqlite3.Connection) -> None:
    for table in (
        "sales_lines_v6", "sales_records_v6", "stocktake_lines_v6", "stocktakes_v6",
        "payroll_lines_v6", "payrolls_v6", "income_records_v6", "expenses_v6",
        "products_v6", "sale_categories_v6", "expense_categories_v6", "employees_v6",
        "suppliers_v6", "reminders_v6", "assets_v6", "import_batches_v6",
        "settings_v6", "security_settings",
    ):
        conn.execute(f"DELETE FROM {table}")


def state_to_v6(conn: sqlite3.Connection, state: Dict[str, Any]) -> None:
    """Materialize a legacy state snapshot into relational tables."""
    create_schema_v6(conn)
    clear_v6_data(conn)
    now = _now()
    settings = dict(state.get("settings", {}))
    password_hash = settings.pop("passwordHash", None)
    for key, value in settings.items():
        conn.execute(
            "INSERT INTO settings_v6(key,value,value_type,updated_at) VALUES(?,?,?,?)",
            (str(key), json.dumps(value, ensure_ascii=False), "json", now),
        )
    conn.execute(
        "INSERT INTO security_settings(id,password_hash,recovery_hash,password_changed_at,updated_at) VALUES(1,?,?,?,?)",
        (password_hash, None, now if password_hash else None, now),
    )

    for index, row in enumerate(state.get("saleCategories", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute(
            "INSERT INTO sale_categories_v6(id,uid,name,active,sort_order,legacy_json) VALUES(?,?,?,?,?,?)",
            (legacy_id, _uid("sale-category", legacy_id, str(index)), str(row.get("name", "")), int(bool(row.get("active", True))), index,
             _json_extra(row, ("id", "name", "active"))),
        )
    expense_category_ids: Dict[str, int] = {}
    for index, row in enumerate(state.get("expenseCategories", [])):
        legacy_id = int(row.get("id") or index + 1)
        name = str(row.get("name", ""))
        expense_category_ids.setdefault(name, legacy_id)
        conn.execute(
            "INSERT INTO expense_categories_v6(id,uid,name,active,sort_order,legacy_json) VALUES(?,?,?,?,?,?)",
            (legacy_id, _uid("expense-category", legacy_id, str(index)), name, int(bool(row.get("active", True))), index,
             _json_extra(row, ("id", "name", "active"))),
        )

    product_names: Dict[int, str] = {}
    for index, row in enumerate(state.get("products", [])):
        legacy_id = int(row.get("id") or index + 1)
        product_names[legacy_id] = str(row.get("name", ""))
        conn.execute(
            """INSERT INTO products_v6(id,uid,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (legacy_id, _uid("product", legacy_id, str(index)), str(row.get("name", "")), str(row.get("category", "")),
             str(row.get("brand", "")), str(row.get("spec", "")), str(row.get("unit", "")), int(bool(row.get("stocktake", False))),
             int(bool(row.get("reminder", False))), int(bool(row.get("active", True))), row.get("createdAt"),
             _json_extra(row, ("id", "name", "category", "brand", "spec", "unit", "stocktake", "reminder", "active", "createdAt"))),
        )

    for index, row in enumerate(state.get("incomeRecords", [])):
        legacy_id = int(row.get("id") or index + 1)
        hall = row.get("hall")
        room = row.get("room")
        dine_in = row.get("dineIn", (float(hall or 0) + float(room or 0)))
        date_value = str(row.get("date", ""))
        conn.execute(
            """INSERT INTO income_records_v6(id,uid,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (legacy_id, _uid("income", legacy_id, str(index)), date_value, str(row.get("entryMode", "day")),
             str(row.get("periodStart") or date_value), str(row.get("periodEnd") or date_value), yuan_to_cents(dine_in),
             None if hall is None else yuan_to_cents(hall), None if room is None else yuan_to_cents(room),
             yuan_to_cents(row.get("chess", 0)), yuan_to_cents(row.get("delivery", 0)), str(row.get("note", "")),
             _json_extra(row, ("id", "date", "entryMode", "periodStart", "periodEnd", "dineIn", "hall", "room", "chess", "delivery", "note"))),
        )

    for index, row in enumerate(state.get("expenses", [])):
        legacy_id = int(row.get("id") or index + 1)
        category = str(row.get("category", ""))
        product_id = row.get("productId")
        conn.execute(
            """INSERT INTO expenses_v6(id,uid,expense_date,mode,category_id,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,product_name_snapshot,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (legacy_id, _uid("expense", legacy_id, str(index)), str(row.get("date", "")), str(row.get("mode", "")),
             expense_category_ids.get(category), category, str(row.get("item", "")), yuan_to_cents(row.get("amount", 0)),
             str(row.get("handler", "")), str(row.get("status", "有效")), str(row.get("note", "")), row.get("purchaseNo"),
             product_id, product_names.get(int(product_id)) if product_id not in (None, "") else None, row.get("qty"), row.get("unit"),
             None if row.get("price") is None else yuan_to_cents(row.get("price")), row.get("importBatchId"),
             _json_extra(row, ("id", "date", "mode", "category", "item", "amount", "handler", "status", "note", "purchaseNo", "productId", "qty", "unit", "price", "importBatchId"))),
        )

    for index, row in enumerate(state.get("salesRecords", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute("INSERT INTO sales_records_v6(id,uid,sale_date,legacy_json) VALUES(?,?,?,?)",
                     (legacy_id, _uid("sales", legacy_id, str(index)), str(row.get("date", "")), _json_extra(row, ("id", "date", "rows"))))
        for line in row.get("rows", []):
            conn.execute(
                "INSERT INTO sales_lines_v6(sales_record_id,category_id,category_name_snapshot,quantity,amount_cents,legacy_json) VALUES(?,?,?,?,?,?)",
                (legacy_id, line.get("categoryId"), str(line.get("category", "")), float(line.get("qty", 0) or 0), yuan_to_cents(line.get("amount", 0)),
                 _json_extra(line, ("categoryId", "category", "qty", "amount"))),
            )

    for index, row in enumerate(state.get("stocktakes", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute("INSERT INTO stocktakes_v6(id,uid,stocktake_date,kind,legacy_json) VALUES(?,?,?,?,?)",
                     (legacy_id, _uid("stocktake", legacy_id, str(index)), str(row.get("date", "")), str(row.get("kind", "")), _json_extra(row, ("id", "date", "kind", "rows"))))
        for line in row.get("rows", []):
            conn.execute(
                """INSERT INTO stocktake_lines_v6(stocktake_id,product_id,product_name_snapshot,unit_snapshot,previous_quantity,actual_quantity,change_quantity,note,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (legacy_id, line.get("productId"), str(line.get("product", "")), str(line.get("unit", "")), float(line.get("previous", 0) or 0),
                 float(line.get("actual", 0) or 0), float(line.get("change", 0) or 0), str(line.get("note", "")),
                 _json_extra(line, ("productId", "product", "unit", "previous", "actual", "change", "note"))),
            )

    for index, row in enumerate(state.get("employees", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute(
            "INSERT INTO employees_v6(id,uid,name,role,standard_salary_cents,start_date,active,legacy_json) VALUES(?,?,?,?,?,?,?,?)",
            (legacy_id, _uid("employee", legacy_id, str(index)), str(row.get("name", "")), str(row.get("role", "")), yuan_to_cents(row.get("salary", 0)),
             str(row.get("startDate", "")), int(bool(row.get("active", True))), _json_extra(row, ("id", "name", "role", "salary", "startDate", "active"))),
        )

    for index, row in enumerate(state.get("payrolls", [])):
        month = str(row.get("month", ""))
        uid = _uid("payroll", month, str(index))
        cursor = conn.execute("INSERT INTO payrolls_v6(uid,month,confirmed,legacy_json) VALUES(?,?,?,?)",
                              (uid, month, int(bool(row.get("confirmed", False))), _json_extra(row, ("month", "confirmed", "rows"))))
        payroll_id = int(cursor.lastrowid)
        for line in row.get("rows", []):
            conn.execute(
                """INSERT INTO payroll_lines_v6(payroll_id,employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (payroll_id, line.get("employeeId"), str(line.get("name", "")), str(line.get("role", "")), yuan_to_cents(line.get("standard", 0)),
                 yuan_to_cents(line.get("amount", 0)), str(line.get("note", "")), _json_extra(line, ("employeeId", "name", "role", "standard", "amount", "note"))),
            )

    for index, row in enumerate(state.get("suppliers", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute(
            "INSERT INTO suppliers_v6(id,uid,name,contact,phone,qualification,note,active,legacy_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (legacy_id, _uid("supplier", legacy_id, str(index)), str(row.get("name", "")), str(row.get("contact", "")), str(row.get("phone", "")),
             str(row.get("qualification", "")), str(row.get("note", "")), int(bool(row.get("active", True))),
             _json_extra(row, ("id", "name", "contact", "phone", "qualification", "note", "active"))),
        )

    product_id_by_name = {name: pid for pid, name in product_names.items()}
    for index, row in enumerate(state.get("reminders", [])):
        legacy_id = int(row.get("id") or index + 1)
        product = str(row.get("product", ""))
        conn.execute(
            "INSERT INTO reminders_v6(id,uid,name,product_id,product_name_snapshot,next_date,cycle_days,done,legacy_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (legacy_id, _uid("reminder", legacy_id, str(index)), str(row.get("name", "")), product_id_by_name.get(product), product,
             str(row.get("date", "")), int(row.get("cycle", 0) or 0), int(bool(row.get("done", False))),
             _json_extra(row, ("id", "name", "product", "date", "cycle", "done"))),
        )

    for index, row in enumerate(state.get("assets", [])):
        legacy_id = int(row.get("id") or index + 1)
        conn.execute(
            "INSERT INTO assets_v6(id,uid,asset_type,name,quantity,unit,record_date,amount_cents,status,note,legacy_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (legacy_id, _uid("asset", legacy_id, str(index)), str(row.get("type", "asset")), str(row.get("name", "")), float(row.get("qty", 0) or 0),
             str(row.get("unit", "")), str(row.get("date", "")), yuan_to_cents(row.get("amount", 0)), str(row.get("status", "")), str(row.get("note", "")),
             _json_extra(row, ("id", "type", "name", "qty", "unit", "date", "amount", "status", "note"))),
        )

    for row in state.get("importBatches", []):
        batch_id = str(row.get("id", ""))
        if not batch_id:
            continue
        conn.execute("INSERT INTO import_batches_v6(id,file_name,imported_at,payload_json) VALUES(?,?,?,?)",
                     (batch_id, str(row.get("file", "")), str(row.get("importedAt", "")), json.dumps(row, ensure_ascii=False, separators=(",", ":"))))


def validate_v6(conn: sqlite3.Connection, state: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    checks["integrity"] = integrity[0] if integrity else "missing"
    foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
    checks["foreignKeyErrors"] = len(foreign)
    expected = {
        "income_records_v6": len(state.get("incomeRecords", [])),
        "expenses_v6": len(state.get("expenses", [])),
        "products_v6": len(state.get("products", [])),
        "sales_records_v6": len(state.get("salesRecords", [])),
        "stocktakes_v6": len(state.get("stocktakes", [])),
        "employees_v6": len(state.get("employees", [])),
        "payrolls_v6": len(state.get("payrolls", [])),
        "suppliers_v6": len(state.get("suppliers", [])),
        "reminders_v6": len(state.get("reminders", [])),
        "assets_v6": len(state.get("assets", [])),
    }
    counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in expected}
    checks["counts"] = counts
    checks["expectedCounts"] = expected
    if counts != expected:
        raise ValueError(f"关系表记录数校验失败：{counts} != {expected}")
    legacy_expense_cents = sum(yuan_to_cents(row.get("amount", 0)) for row in state.get("expenses", []))
    v6_expense_cents = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6").fetchone()[0])
    checks["expenseCents"] = v6_expense_cents
    if legacy_expense_cents != v6_expense_cents:
        raise ValueError(f"支出金额校验失败：{legacy_expense_cents} != {v6_expense_cents}")
    legacy_income_cents = sum(
        yuan_to_cents(row.get("dineIn", float(row.get("hall", 0) or 0) + float(row.get("room", 0) or 0)))
        + yuan_to_cents(row.get("chess", 0)) + yuan_to_cents(row.get("delivery", 0))
        for row in state.get("incomeRecords", [])
    )
    v6_income_cents = int(conn.execute("SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6").fetchone()[0])
    checks["incomeCents"] = v6_income_cents
    if legacy_income_cents != v6_income_cents:
        raise ValueError(f"收入金额校验失败：{legacy_income_cents} != {v6_income_cents}")
    if checks["integrity"] != "ok" or checks["foreignKeyErrors"]:
        raise ValueError(f"SQLite 完整性校验失败：{checks}")
    return checks


def relational_state_available(conn: sqlite3.Connection) -> bool:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "schema_migrations" not in tables or "expenses_v6" not in tables:
        return False
    row = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (RELATIONAL_SCHEMA_VERSION,)).fetchone()
    return row is not None


def build_relational_state(conn: sqlite3.Connection, base_state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build the compatibility API response exclusively from relational tables."""
    state = dict(base_state or {})
    settings = {}
    for key, value in conn.execute("SELECT key,value FROM settings_v6 ORDER BY key"):
        settings[key] = json.loads(value)
    security = conn.execute("SELECT password_hash FROM security_settings WHERE id=1").fetchone()
    if security and security[0]:
        settings["passwordHash"] = security[0]
    state["settings"] = settings
    state["schemaVersion"] = RELATIONAL_SCHEMA_VERSION

    state["saleCategories"] = [
        {"id": row[0], "name": row[1], "active": bool(row[2]), **(json.loads(row[3]) if row[3] else {})}
        for row in conn.execute("SELECT id,name,active,legacy_json FROM sale_categories_v6 ORDER BY sort_order,id")
    ]
    state["expenseCategories"] = [
        {"id": row[0], "name": row[1], "active": bool(row[2]), **(json.loads(row[3]) if row[3] else {})}
        for row in conn.execute("SELECT id,name,active,legacy_json FROM expense_categories_v6 ORDER BY sort_order,id")
    ]
    state["products"] = []
    for row in conn.execute("SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json FROM products_v6 ORDER BY id"):
        item = {"id": row[0], "name": row[1], "category": row[2], "brand": row[3], "spec": row[4], "unit": row[5], "stocktake": bool(row[6]), "reminder": bool(row[7]), "active": bool(row[8])}
        if row[9]: item["createdAt"] = row[9]
        if row[10]: item.update(json.loads(row[10]))
        state["products"].append(item)

    state["incomeRecords"] = []
    for row in conn.execute("SELECT id,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json FROM income_records_v6 ORDER BY id"):
        item = {"id": row[0], "date": row[1], "entryMode": row[2], "periodStart": row[3], "periodEnd": row[4], "dineIn": cents_to_legacy_number(row[5]), "chess": cents_to_legacy_number(row[8]), "delivery": cents_to_legacy_number(row[9]), "note": row[10]}
        if row[6] is not None: item["hall"] = cents_to_legacy_number(row[6])
        if row[7] is not None: item["room"] = cents_to_legacy_number(row[7])
        if row[11]: item.update(json.loads(row[11]))
        state["incomeRecords"].append(item)

    state["expenses"] = []
    for row in conn.execute("SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json FROM expenses_v6 ORDER BY id"):
        item = {"id": row[0], "date": row[1], "mode": row[2], "category": row[3], "item": row[4], "amount": cents_to_legacy_number(row[5]), "handler": row[6], "status": row[7]}
        if row[8]: item["note"] = row[8]
        if row[9] is not None: item["purchaseNo"] = row[9]
        if row[10] is not None: item["productId"] = row[10]
        if row[11] is not None: item["qty"] = row[11]
        if row[12] is not None: item["unit"] = row[12]
        if row[13] is not None: item["price"] = cents_to_legacy_number(row[13])
        if row[14] is not None: item["importBatchId"] = row[14]
        if row[15]: item.update(json.loads(row[15]))
        state["expenses"].append(item)

    state["salesRecords"] = []
    for record in conn.execute("SELECT id,sale_date,legacy_json FROM sales_records_v6 ORDER BY id"):
        item = {"id": record[0], "date": record[1], "rows": []}
        if record[2]: item.update(json.loads(record[2]))
        for line in conn.execute("SELECT category_id,category_name_snapshot,quantity,amount_cents,legacy_json FROM sales_lines_v6 WHERE sales_record_id=? ORDER BY id", (record[0],)):
            child = {"categoryId": line[0], "category": line[1], "qty": line[2], "amount": cents_to_legacy_number(line[3])}
            if line[4]: child.update(json.loads(line[4]))
            item["rows"].append(child)
        state["salesRecords"].append(item)

    state["stocktakes"] = []
    for record in conn.execute("SELECT id,stocktake_date,kind,legacy_json FROM stocktakes_v6 ORDER BY id"):
        item = {"id": record[0], "date": record[1], "kind": record[2], "rows": []}
        if record[3]: item.update(json.loads(record[3]))
        for line in conn.execute("SELECT product_id,product_name_snapshot,unit_snapshot,previous_quantity,actual_quantity,change_quantity,note,legacy_json FROM stocktake_lines_v6 WHERE stocktake_id=? ORDER BY id", (record[0],)):
            child = {"productId": line[0], "product": line[1], "unit": line[2], "previous": line[3], "actual": line[4], "change": line[5], "note": line[6]}
            if line[7]: child.update(json.loads(line[7]))
            item["rows"].append(child)
        state["stocktakes"].append(item)

    state["employees"] = [
        {"id": row[0], "name": row[1], "role": row[2], "salary": cents_to_legacy_number(row[3]), "startDate": row[4], "active": bool(row[5]), **(json.loads(row[6]) if row[6] else {})}
        for row in conn.execute("SELECT id,name,role,standard_salary_cents,start_date,active,legacy_json FROM employees_v6 ORDER BY id")
    ]
    state["payrolls"] = []
    for record in conn.execute("SELECT id,month,confirmed,legacy_json FROM payrolls_v6 ORDER BY month,id"):
        item = {"month": record[1], "confirmed": bool(record[2]), "rows": []}
        if record[3]: item.update(json.loads(record[3]))
        for line in conn.execute("SELECT employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note,legacy_json FROM payroll_lines_v6 WHERE payroll_id=? ORDER BY id", (record[0],)):
            child = {"employeeId": line[0], "name": line[1], "role": line[2], "standard": cents_to_legacy_number(line[3]), "amount": cents_to_legacy_number(line[4]), "note": line[5]}
            if line[6]: child.update(json.loads(line[6]))
            item["rows"].append(child)
        state["payrolls"].append(item)

    state["suppliers"] = [
        {"id": row[0], "name": row[1], "contact": row[2], "phone": row[3], "qualification": row[4], "note": row[5], "active": bool(row[6]), **(json.loads(row[7]) if row[7] else {})}
        for row in conn.execute("SELECT id,name,contact,phone,qualification,note,active,legacy_json FROM suppliers_v6 ORDER BY id")
    ]
    state["reminders"] = [
        {"id": row[0], "name": row[1], "product": row[2], "date": row[3], "cycle": row[4], "done": bool(row[5]), **(json.loads(row[6]) if row[6] else {})}
        for row in conn.execute("SELECT id,name,product_name_snapshot,next_date,cycle_days,done,legacy_json FROM reminders_v6 ORDER BY id")
    ]
    state["assets"] = [
        {"id": row[0], "type": row[1], "name": row[2], "qty": row[3], "unit": row[4], "date": row[5], "amount": cents_to_legacy_number(row[6]), "status": row[7], "note": row[8], **(json.loads(row[9]) if row[9] else {})}
        for row in conn.execute("SELECT id,asset_type,name,quantity,unit,record_date,amount_cents,status,note,legacy_json FROM assets_v6 ORDER BY id")
    ]
    state["importBatches"] = [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM import_batches_v6 ORDER BY imported_at,id")]
    return state
