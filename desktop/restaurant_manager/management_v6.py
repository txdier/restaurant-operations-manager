from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .money import cents_to_legacy_number, yuan_to_cents
from .storage_v6 import _uid


def _legacy_state(conn) -> Dict[str, Any]:
    row = conn.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
    if not row:
        raise RuntimeError("本地数据库缺少兼容状态")
    return json.loads(row[0])


def _write_state(conn, state: Dict[str, Any], event: str, detail: Dict[str, Any]) -> None:
    conn.execute("UPDATE app_state SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=1", (json.dumps(state, ensure_ascii=False, separators=(",", ":")),))
    conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", (event, json.dumps(detail, ensure_ascii=False, separators=(",", ":"))))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('relational_snapshot_dirty','0')")


def stocktake_form_v6(database: Any, record_date: str, kind: str) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        existing = conn.execute("SELECT id FROM stocktakes_v6 WHERE stocktake_date=? AND kind=? ORDER BY id LIMIT 1", (record_date, kind)).fetchone()
        existing_id = int(existing[0]) if existing else None
        products = {
            int(row[0]): {"id": int(row[0]), "name": str(row[1]), "brand": str(row[2]), "spec": str(row[3]), "unit": str(row[4]), "active": bool(row[5])}
            for row in conn.execute("SELECT id,name,brand,spec,unit,active FROM products_v6 WHERE stocktake_enabled=1 AND active=1 ORDER BY name,id")
        }
        existing_lines: Dict[int, Dict[str, Any]] = {}
        if existing_id:
            for row in conn.execute("SELECT product_id,product_name_snapshot,unit_snapshot,previous_quantity,actual_quantity,note FROM stocktake_lines_v6 WHERE stocktake_id=? ORDER BY id", (existing_id,)):
                pid = int(row[0]) if row[0] is not None else 0
                existing_lines[pid] = {"productId": pid or None, "product": str(row[1]), "unit": str(row[2]), "previous": float(row[3]), "actual": float(row[4]), "note": str(row[5])}
                if pid and pid not in products:
                    product_row = conn.execute("SELECT id,name,brand,spec,unit,active FROM products_v6 WHERE id=?", (pid,)).fetchone()
                    if product_row:
                        products[pid] = {"id": pid, "name": str(product_row[1]), "brand": str(product_row[2]), "spec": str(product_row[3]), "unit": str(product_row[4]), "active": bool(product_row[5])}
        rows: List[Dict[str, Any]] = []
        for product_id, product in products.items():
            if product_id in existing_lines:
                line = existing_lines[product_id]
                rows.append({**product, **line})
                continue
            prior = conn.execute(
                """SELECT l.actual_quantity FROM stocktake_lines_v6 l JOIN stocktakes_v6 s ON s.id=l.stocktake_id
                   WHERE l.product_id=? AND s.stocktake_date<? ORDER BY s.stocktake_date DESC,s.id DESC,l.id DESC LIMIT 1""",
                (product_id, record_date),
            ).fetchone()
            previous = float(prior[0]) if prior else 0.0
            rows.append({**product, "productId": product_id, "product": product["name"], "previous": previous, "actual": previous, "note": ""})
    return {"id": existing_id, "date": record_date, "kind": kind, "rows": rows}


def save_stocktake_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    record_date = str(payload.get("date", "")).strip()
    kind = str(payload.get("kind", "月底盘点")).strip() or "月底盘点"
    rows = payload.get("rows")
    if not record_date or not isinstance(rows, list):
        raise ValueError("盘点日期或明细无效")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id FROM stocktakes_v6 WHERE stocktake_date=? AND kind=? ORDER BY id LIMIT 1", (record_date, kind)).fetchone()
        if existing:
            stocktake_id = int(existing[0])
            conn.execute("DELETE FROM stocktake_lines_v6 WHERE stocktake_id=?", (stocktake_id,))
            conn.execute("UPDATE stocktakes_v6 SET legacy_json='' WHERE id=?", (stocktake_id,))
            event = "stocktake.update"
        else:
            stocktake_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM stocktakes_v6").fetchone()[0])
            conn.execute("INSERT INTO stocktakes_v6(id,uid,stocktake_date,kind,legacy_json) VALUES(?,?,?,?,?)", (stocktake_id, _uid("stocktake", stocktake_id, str(stocktake_id)), record_date, kind, ""))
            event = "stocktake.create"
        saved: List[Dict[str, Any]] = []
        for index, line in enumerate(rows, 1):
            product_id = int(line.get("productId") or 0)
            product = conn.execute("SELECT name,unit FROM products_v6 WHERE id=?", (product_id,)).fetchone()
            if not product:
                raise ValueError(f"第 {index} 行商品不存在")
            previous = float(line.get("previous", 0) or 0)
            actual = float(line.get("actual", 0) or 0)
            if actual < 0:
                raise ValueError(f"第 {index} 行实际数量不能小于 0")
            item = {"productId": product_id, "product": str(product[0]), "unit": str(product[1]), "previous": previous, "actual": actual, "change": actual - previous, "note": str(line.get("note", ""))}
            conn.execute(
                """INSERT INTO stocktake_lines_v6(stocktake_id,product_id,product_name_snapshot,unit_snapshot,previous_quantity,actual_quantity,change_quantity,note,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (stocktake_id, product_id, item["product"], item["unit"], previous, actual, actual - previous, item["note"], ""),
            )
            saved.append(item)
        state = _legacy_state(conn)
        record = {"id": stocktake_id, "date": record_date, "kind": kind, "rows": saved}
        values = state.setdefault("stocktakes", [])
        values[:] = [item for item in values if int(item.get("id", 0)) != stocktake_id and not (str(item.get("date", "")) == record_date and str(item.get("kind", "")) == kind)]
        values.append(record)
        _write_state(conn, state, event, {"id": stocktake_id, "lineCount": len(saved)})
        conn.commit()
        return record


def list_reminders_v6(database: Any) -> Dict[str, Any]:
    today = datetime.now().date().isoformat()
    with database.lock, database.connect() as conn:
        items = [
            {"id": int(row[0]), "name": str(row[1]), "productId": row[2], "product": str(row[3]), "date": str(row[4]), "cycle": int(row[5]), "done": bool(row[6])}
            for row in conn.execute("SELECT id,name,product_id,product_name_snapshot,next_date,cycle_days,done FROM reminders_v6 ORDER BY done,next_date,id")
        ]
        products = [
            {"id": int(row[0]), "name": str(row[1]), "unit": str(row[2])}
            for row in conn.execute("SELECT id,name,unit FROM products_v6 WHERE active=1 ORDER BY name,id")
        ]
    return {
        "items": items,
        "products": products,
        "summary": {
            "overdue": sum(1 for item in items if not item["done"] and item["date"] < today),
            "future": sum(1 for item in items if not item["done"] and item["date"] >= today),
            "done": sum(1 for item in items if item["done"]),
        },
    }


def create_reminder_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    product_id = int(payload.get("productId") or 0)
    next_date = str(payload.get("date", "")).strip()
    cycle = max(0, int(payload.get("cycle", 0) or 0))
    if not name or not next_date or not product_id:
        raise ValueError("提醒名称、商品和日期不能为空")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        product = conn.execute("SELECT name FROM products_v6 WHERE id=? AND active=1", (product_id,)).fetchone()
        if not product:
            raise ValueError("商品不存在或已停用")
        reminder_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM reminders_v6").fetchone()[0])
        item = {"id": reminder_id, "name": name, "productId": product_id, "product": str(product[0]), "date": next_date, "cycle": cycle, "done": False}
        conn.execute("INSERT INTO reminders_v6(id,uid,name,product_id,product_name_snapshot,next_date,cycle_days,done,legacy_json) VALUES(?,?,?,?,?,?,?,?,?)", (reminder_id, _uid("reminder", reminder_id, str(reminder_id)), name, product_id, item["product"], next_date, cycle, 0, ""))
        state = _legacy_state(conn)
        state.setdefault("reminders", []).append({key: value for key, value in item.items() if key != "productId"})
        _write_state(conn, state, "reminder.create", {"id": reminder_id})
        conn.commit()
        return item


def finish_reminder_v6(database: Any, reminder_id: int) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id,name,product_id,product_name_snapshot,next_date,cycle_days,done FROM reminders_v6 WHERE id=?", (int(reminder_id),)).fetchone()
        if not row:
            raise ValueError("提醒不存在")
        cycle = int(row[5])
        next_date = str(row[4])
        done = True
        if cycle > 0:
            next_date = (datetime.strptime(next_date, "%Y-%m-%d").date() + timedelta(days=cycle)).isoformat()
            done = False
        conn.execute("UPDATE reminders_v6 SET next_date=?,done=? WHERE id=?", (next_date, int(done), int(reminder_id)))
        item = {"id": int(row[0]), "name": str(row[1]), "productId": row[2], "product": str(row[3]), "date": next_date, "cycle": cycle, "done": done}
        state = _legacy_state(conn)
        for legacy in state.get("reminders", []):
            if int(legacy.get("id", 0)) == int(reminder_id):
                legacy["date"] = next_date
                legacy["done"] = done
                break
        _write_state(conn, state, "reminder.finish", {"id": int(reminder_id), "nextDate": next_date, "done": done})
        conn.commit()
        return item


def delete_reminder_v6(database: Any, reminder_id: int) -> None:
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM reminders_v6 WHERE id=?", (int(reminder_id),))
        state = _legacy_state(conn)
        state["reminders"] = [item for item in state.get("reminders", []) if int(item.get("id", 0)) != int(reminder_id)]
        _write_state(conn, state, "reminder.delete", {"id": int(reminder_id)})
        conn.commit()


def list_employees_v6(database: Any) -> List[Dict[str, Any]]:
    with database.lock, database.connect() as conn:
        return [
            {"id": int(row[0]), "name": str(row[1]), "role": str(row[2]), "salary": cents_to_legacy_number(int(row[3])), "startDate": str(row[4]), "active": bool(row[5])}
            for row in conn.execute("SELECT id,name,role,standard_salary_cents,start_date,active FROM employees_v6 ORDER BY active DESC,id")
        ]


def upsert_employee_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    role = str(payload.get("role", "")).strip()
    start_date = str(payload.get("startDate", "")).strip()
    salary_cents = yuan_to_cents(payload.get("salary", 0))
    if not name or not role or not start_date or salary_cents < 0:
        raise ValueError("员工姓名、岗位、入职日期或标准月薪不正确")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        employee_id = int(payload.get("id") or 0)
        exists = conn.execute("SELECT 1 FROM employees_v6 WHERE id=?", (employee_id,)).fetchone() if employee_id else None
        if not exists:
            employee_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM employees_v6").fetchone()[0])
        item = {"id": employee_id, "name": name, "role": role, "salary": cents_to_legacy_number(salary_cents), "startDate": start_date, "active": bool(payload.get("active", True))}
        if exists:
            conn.execute("UPDATE employees_v6 SET name=?,role=?,standard_salary_cents=?,start_date=?,active=? WHERE id=?", (name, role, salary_cents, start_date, int(item["active"]), employee_id))
            event = "employee.update"
        else:
            conn.execute("INSERT INTO employees_v6(id,uid,name,role,standard_salary_cents,start_date,active,legacy_json) VALUES(?,?,?,?,?,?,?,?)", (employee_id, _uid("employee", employee_id, str(employee_id)), name, role, salary_cents, start_date, int(item["active"]), ""))
            event = "employee.create"
        state = _legacy_state(conn)
        employees = state.setdefault("employees", [])
        found = False
        for index, old in enumerate(employees):
            if int(old.get("id", 0)) == employee_id:
                employees[index] = item
                found = True
                break
        if not found:
            employees.append(item)
        _write_state(conn, state, event, {"id": employee_id})
        conn.commit()
        return item


def get_payroll_v6(database: Any, month: str) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        payroll = conn.execute("SELECT id,confirmed FROM payrolls_v6 WHERE month=?", (month,)).fetchone()
        rows: List[Dict[str, Any]] = []
        if payroll:
            for row in conn.execute("SELECT employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note FROM payroll_lines_v6 WHERE payroll_id=? ORDER BY id", (int(payroll[0]),)):
                rows.append({"employeeId": row[0], "name": str(row[1]), "role": str(row[2]), "standard": cents_to_legacy_number(int(row[3])), "amount": cents_to_legacy_number(int(row[4])), "note": str(row[5])})
        employees = list_employees_v6(database)
    return {"month": month, "confirmed": bool(payroll[1]) if payroll else False, "rows": rows, "employees": employees}


def generate_payroll_v6(database: Any, month: str) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT id,confirmed FROM payrolls_v6 WHERE month=?", (month,)).fetchone()
        if current and bool(current[1]):
            raise ValueError("工资表已确认，请先撤销确认后再重新生成")
        if current:
            payroll_id = int(current[0])
            conn.execute("DELETE FROM payroll_lines_v6 WHERE payroll_id=?", (payroll_id,))
        else:
            cursor = conn.execute("INSERT INTO payrolls_v6(uid,month,confirmed,legacy_json) VALUES(?,?,0,'')", (_uid("payroll", month, month), month))
            payroll_id = int(cursor.lastrowid)
        rows: List[Dict[str, Any]] = []
        for employee in conn.execute("SELECT id,name,role,standard_salary_cents FROM employees_v6 WHERE active=1 ORDER BY id"):
            conn.execute("INSERT INTO payroll_lines_v6(payroll_id,employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note,legacy_json) VALUES(?,?,?,?,?,?,?,?)", (payroll_id, int(employee[0]), str(employee[1]), str(employee[2]), int(employee[3]), int(employee[3]), "", ""))
            rows.append({"employeeId": int(employee[0]), "name": str(employee[1]), "role": str(employee[2]), "standard": cents_to_legacy_number(int(employee[3])), "amount": cents_to_legacy_number(int(employee[3])), "note": ""})
        state = _legacy_state(conn)
        snapshot = {"month": month, "confirmed": False, "rows": rows}
        payrolls = state.setdefault("payrolls", [])
        payrolls[:] = [item for item in payrolls if str(item.get("month", "")) != month]
        payrolls.append(snapshot)
        _write_state(conn, state, "payroll.generate", {"month": month, "lineCount": len(rows)})
        conn.commit()
        return snapshot


def save_payroll_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    month = str(payload.get("month", "")).strip()
    rows = payload.get("rows")
    confirmed = bool(payload.get("confirmed", False))
    if not month or not isinstance(rows, list):
        raise ValueError("工资月份或明细无效")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        payroll = conn.execute("SELECT id,confirmed FROM payrolls_v6 WHERE month=?", (month,)).fetchone()
        if not payroll:
            raise ValueError("工资表尚未生成")
        payroll_id = int(payroll[0])
        was_confirmed = bool(payroll[1])
        if was_confirmed and confirmed:
            raise ValueError("工资表已确认，如需修改请先撤销确认")
        existing = {int(row[0]): row for row in conn.execute("SELECT employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents FROM payroll_lines_v6 WHERE payroll_id=?", (payroll_id,)) if row[0] is not None}
        if not was_confirmed:
            for line in rows:
                employee_id = int(line.get("employeeId") or 0)
                snapshot = existing.get(employee_id)
                if not snapshot:
                    continue
                amount_cents = yuan_to_cents(line.get("amount", 0))
                if amount_cents < 0:
                    raise ValueError("本月工资不能小于 0")
                conn.execute("UPDATE payroll_lines_v6 SET actual_salary_cents=?,note=? WHERE payroll_id=? AND employee_id=?", (amount_cents, str(line.get("note", "")), payroll_id, employee_id))
        conn.execute("UPDATE payrolls_v6 SET confirmed=? WHERE id=?", (int(confirmed), payroll_id))
        saved_rows = [
            {"employeeId": row[0], "name": str(row[1]), "role": str(row[2]), "standard": cents_to_legacy_number(int(row[3])), "amount": cents_to_legacy_number(int(row[4])), "note": str(row[5])}
            for row in conn.execute("SELECT employee_id,employee_name_snapshot,role_snapshot,standard_salary_cents,actual_salary_cents,note FROM payroll_lines_v6 WHERE payroll_id=? ORDER BY id", (payroll_id,))
        ]
        state = _legacy_state(conn)
        snapshot_state = {"month": month, "confirmed": confirmed, "rows": saved_rows}
        payrolls = state.setdefault("payrolls", [])
        payrolls[:] = [item for item in payrolls if str(item.get("month", "")) != month]
        payrolls.append(snapshot_state)
        _write_state(conn, state, "payroll.save", {"month": month, "confirmed": confirmed})
        conn.commit()
        return snapshot_state


def list_suppliers_v6(database: Any) -> List[Dict[str, Any]]:
    with database.lock, database.connect() as conn:
        return [
            {"id": int(row[0]), "name": str(row[1]), "contact": str(row[2]), "phone": str(row[3]), "qualification": str(row[4]), "note": str(row[5]), "active": bool(row[6])}
            for row in conn.execute("SELECT id,name,contact,phone,qualification,note,active FROM suppliers_v6 ORDER BY active DESC,name,id")
        ]


def upsert_supplier_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("供应商名称不能为空")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        supplier_id = int(payload.get("id") or 0)
        exists = conn.execute("SELECT 1 FROM suppliers_v6 WHERE id=?", (supplier_id,)).fetchone() if supplier_id else None
        if not exists:
            supplier_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM suppliers_v6").fetchone()[0])
        item = {"id": supplier_id, "name": name, "contact": str(payload.get("contact", "")), "phone": str(payload.get("phone", "")), "qualification": str(payload.get("qualification", "")), "note": str(payload.get("note", "")), "active": bool(payload.get("active", True))}
        if exists:
            conn.execute("UPDATE suppliers_v6 SET name=?,contact=?,phone=?,qualification=?,note=?,active=? WHERE id=?", (item["name"], item["contact"], item["phone"], item["qualification"], item["note"], int(item["active"]), supplier_id))
            event = "supplier.update"
        else:
            conn.execute("INSERT INTO suppliers_v6(id,uid,name,contact,phone,qualification,note,active,legacy_json) VALUES(?,?,?,?,?,?,?,?,?)", (supplier_id, _uid("supplier", supplier_id, str(supplier_id)), item["name"], item["contact"], item["phone"], item["qualification"], item["note"], int(item["active"]), ""))
            event = "supplier.create"
        state = _legacy_state(conn)
        suppliers = state.setdefault("suppliers", [])
        found = False
        for index, old in enumerate(suppliers):
            if int(old.get("id", 0)) == supplier_id:
                suppliers[index] = item
                found = True
                break
        if not found:
            suppliers.append(item)
        _write_state(conn, state, event, {"id": supplier_id})
        conn.commit()
        return item
