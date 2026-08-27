from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from .money import cents_to_legacy_number, yuan_to_cents
from .storage_v6 import _json_extra, _uid


def dashboard_detail_v6(database: Any, day: str) -> Dict[str, Any]:
    current = datetime.strptime(day, "%Y-%m-%d").date()
    month_start = current.replace(day=1).isoformat()
    if current.month == 12:
        next_month = current.replace(year=current.year + 1, month=1, day=1)
    else:
        next_month = current.replace(month=current.month + 1, day=1)
    month_end = (next_month - timedelta(days=1)).isoformat()
    seven_start = (current - timedelta(days=6)).isoformat()
    with database.lock, database.connect() as conn:
        income_today = int(conn.execute("SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date=?", (day,)).fetchone()[0])
        expense_today = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date=? AND status='有效'", (day,)).fetchone()[0])
        income_month = int(conn.execute("SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date BETWEEN ? AND ?", (month_start, month_end)).fetchone()[0])
        expense_month = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date BETWEEN ? AND ? AND status='有效'", (month_start, month_end)).fetchone()[0])
        incomes = {str(row[0]): int(row[1]) for row in conn.execute(
            "SELECT record_date,COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date BETWEEN ? AND ? GROUP BY record_date",
            (seven_start, day),
        )}
        expenses = {str(row[0]): int(row[1]) for row in conn.execute(
            "SELECT expense_date,COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date BETWEEN ? AND ? AND status='有效' GROUP BY expense_date",
            (seven_start, day),
        )}
        categories = [
            {"name": str(row[0]), "amount": cents_to_legacy_number(int(row[1]))}
            for row in conn.execute(
                "SELECT category_name_snapshot,SUM(amount_cents) amount FROM expenses_v6 WHERE expense_date BETWEEN ? AND ? AND status='有效' GROUP BY category_name_snapshot ORDER BY amount DESC LIMIT 8",
                (month_start, month_end),
            )
        ]
        pending = int(conn.execute("SELECT COUNT(*) FROM reminders_v6 WHERE done=0").fetchone()[0])
    trend: List[Dict[str, Any]] = []
    for offset in range(7):
        current_day = current - timedelta(days=6 - offset)
        key = current_day.isoformat()
        trend.append({
            "date": key,
            "income": cents_to_legacy_number(incomes.get(key, 0)),
            "expense": cents_to_legacy_number(expenses.get(key, 0)),
        })
    return {
        "todayIncome": cents_to_legacy_number(income_today),
        "todayExpense": cents_to_legacy_number(expense_today),
        "monthIncome": cents_to_legacy_number(income_month),
        "monthExpense": cents_to_legacy_number(expense_month),
        "monthBalance": cents_to_legacy_number(income_month - expense_month),
        "pendingReminders": pending,
        "trend": trend,
        "categories": categories,
    }


def get_sales_record_v6(database: Any, record_date: str) -> Dict[str, Any]:
    with database.lock, database.connect() as conn:
        record = conn.execute("SELECT id,sale_date,legacy_json FROM sales_records_v6 WHERE sale_date=? ORDER BY id LIMIT 1", (record_date,)).fetchone()
        categories = [
            {"id": int(row[0]), "name": str(row[1]), "active": bool(row[2])}
            for row in conn.execute("SELECT id,name,active FROM sale_categories_v6 ORDER BY sort_order,id")
        ]
        income_cents = int(conn.execute(
            "SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE entry_mode='day' AND record_date=?",
            (record_date,),
        ).fetchone()[0])
        rows: List[Dict[str, Any]] = []
        record_id = None
        if record:
            record_id = int(record[0])
            rows = [
                {
                    "categoryId": line[0],
                    "category": str(line[1]),
                    "qty": float(line[2]),
                    "amount": cents_to_legacy_number(int(line[3])),
                }
                for line in conn.execute("SELECT category_id,category_name_snapshot,quantity,amount_cents FROM sales_lines_v6 WHERE sales_record_id=? ORDER BY id", (record_id,))
            ]
    return {"id": record_id, "date": record_date, "rows": rows, "categories": categories, "dailyIncome": cents_to_legacy_number(income_cents)}


def save_sales_record_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    record_date = str(payload.get("date", "")).strip()
    rows = payload.get("rows")
    if not record_date:
        raise ValueError("销售日期不能为空")
    if not isinstance(rows, list):
        raise ValueError("销售分类数据无效")
    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        categories = {int(row[0]): str(row[1]) for row in conn.execute("SELECT id,name FROM sale_categories_v6")}
        existing = conn.execute("SELECT id FROM sales_records_v6 WHERE sale_date=? ORDER BY id LIMIT 1", (record_date,)).fetchone()
        if existing:
            record_id = int(existing[0])
            conn.execute("DELETE FROM sales_lines_v6 WHERE sales_record_id=?", (record_id,))
            conn.execute("UPDATE sales_records_v6 SET legacy_json='' WHERE id=?", (record_id,))
            event = "sales.update"
        else:
            record_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM sales_records_v6").fetchone()[0])
            conn.execute("INSERT INTO sales_records_v6(id,uid,sale_date,legacy_json) VALUES(?,?,?,?)", (record_id, _uid("sales", record_id, str(record_id)), record_date, ""))
            event = "sales.create"
        saved: List[Dict[str, Any]] = []
        for row in rows:
            category_id = int(row.get("categoryId") or 0)
            category = categories.get(category_id, str(row.get("category", "")))
            quantity = float(row.get("qty", 0) or 0)
            amount_cents = yuan_to_cents(row.get("amount", 0))
            if quantity < 0 or amount_cents < 0:
                raise ValueError("销售数量和金额不能为负数")
            conn.execute(
                "INSERT INTO sales_lines_v6(sales_record_id,category_id,category_name_snapshot,quantity,amount_cents,legacy_json) VALUES(?,?,?,?,?,?)",
                (record_id, category_id or None, category, quantity, amount_cents, _json_extra(row, ("categoryId", "category", "qty", "amount"))),
            )
            saved.append({"categoryId": category_id or None, "category": category, "qty": quantity, "amount": cents_to_legacy_number(amount_cents)})
        record_state = {"id": record_id, "date": record_date, "rows": saved}
        conn.execute("INSERT INTO audit_log(event,detail) VALUES(?,?)", (event, json.dumps({"id": record_id, "date": record_date, "lineCount": len(saved)}, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()
        return record_state
