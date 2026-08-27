from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .money import cents_to_legacy_number, yuan_to_cents
from .storage_v6 import _json_extra, _uid


EXPENSE_SORT_COLUMNS = {
    "date": "expense_date",
    "amount": "amount_cents",
    "category": "category_name_snapshot",
    "handler": "handler",
    "mode": "mode",
    "status": "status",
    "id": "id",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _audit(conn, event: str, detail: Dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log(event,detail) VALUES(?,?)",
        (event, json.dumps(detail, ensure_ascii=False, separators=(",", ":"))),
    )


def _expense_from_row(row) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": row[0],
        "date": row[1],
        "mode": row[2],
        "category": row[3],
        "item": row[4],
        "amount": cents_to_legacy_number(row[5]),
        "handler": row[6],
        "status": row[7],
    }
    if row[8]:
        item["note"] = row[8]
    if row[9] is not None:
        item["purchaseNo"] = row[9]
    if row[10] is not None:
        item["productId"] = row[10]
    if row[11] is not None:
        item["qty"] = row[11]
    if row[12] is not None:
        item["unit"] = row[12]
    if row[13] is not None:
        item["price"] = cents_to_legacy_number(row[13])
    if row[14] is not None:
        item["importBatchId"] = row[14]
    if row[15]:
        item.update(json.loads(row[15]))
    return item


def _product_from_row(row) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "brand": row[3],
        "spec": row[4],
        "unit": row[5],
        "stocktake": bool(row[6]),
        "reminder": bool(row[7]),
        "active": bool(row[8]),
    }
    if row[9]:
        item["createdAt"] = row[9]
    if row[10]:
        item.update(json.loads(row[10]))
    return item


def _income_from_row(row) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": row[0],
        "date": row[1],
        "entryMode": row[2],
        "periodStart": row[3],
        "periodEnd": row[4],
        "dineIn": cents_to_legacy_number(row[5]),
        "chess": cents_to_legacy_number(row[8]),
        "delivery": cents_to_legacy_number(row[9]),
        "note": row[10],
    }
    if row[6] is not None:
        item["hall"] = cents_to_legacy_number(row[6])
    if row[7] is not None:
        item["room"] = cents_to_legacy_number(row[7])
    if row[11]:
        item.update(json.loads(row[11]))
    return item


class V6Repository:
    """Transactional access to schema-v6 relational tables."""

    def __init__(self, database: Any) -> None:
        self.database = database

    def _category_id(self, conn, name: str) -> Optional[int]:
        row = conn.execute("SELECT id FROM expense_categories_v6 WHERE name=? ORDER BY id LIMIT 1", (name,)).fetchone()
        return int(row[0]) if row else None

    def _product_name(self, conn, product_id: Any) -> Optional[str]:
        if product_id in (None, ""):
            return None
        row = conn.execute("SELECT name FROM products_v6 WHERE id=?", (int(product_id),)).fetchone()
        return str(row[0]) if row else None

    def list_expenses(
        self,
        *,
        start: str = "",
        end: str = "",
        category: str = "",
        handler: str = "",
        status: str = "",
        keyword: str = "",
        sort_by: str = "date",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 50)))
        clauses: List[str] = []
        values: List[Any] = []
        if start:
            clauses.append("expense_date>=?")
            values.append(start)
        if end:
            clauses.append("expense_date<=?")
            values.append(end)
        if category and category != "全部类别":
            clauses.append("category_name_snapshot=?")
            values.append(category)
        if handler and handler != "全部经手人":
            clauses.append("handler=?")
            values.append(handler)
        if status and status != "全部":
            clauses.append("status=?")
            values.append(status)
        if keyword:
            token = f"%{keyword.strip().lower()}%"
            clauses.append("LOWER(item || ' ' || category_name_snapshot || ' ' || handler || ' ' || mode || ' ' || status || ' ' || note) LIKE ?")
            values.append(token)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        column = EXPENSE_SORT_COLUMNS.get(sort_by, "expense_date")
        direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
        select = "SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json FROM expenses_v6"
        with self.database.lock, self.database.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM expenses_v6" + where, values).fetchone()[0])
            summary_cents = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6" + where, values).fetchone()[0])
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"{select}{where} ORDER BY {column} {direction}, id {direction} LIMIT ? OFFSET ?",
                [*values, page_size, offset],
            ).fetchall()
        return {
            "items": [_expense_from_row(row) for row in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
            "amountTotal": cents_to_legacy_number(summary_cents),
        }

    def recent_expenses(self, limit: int = 20, status: str = "有效") -> List[Dict[str, Any]]:
        limit = min(100, max(1, int(limit or 20)))
        where = "" if not status or status == "全部" else " WHERE status=?"
        params: List[Any] = [] if not where else [status]
        sql = (
            "SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json "
            f"FROM expenses_v6{where} ORDER BY expense_date DESC,id DESC LIMIT ?"
        )
        with self.database.lock, self.database.connect() as conn:
            rows = conn.execute(sql, [*params, limit]).fetchall()
        return [_expense_from_row(row) for row in rows]

    def create_expense(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        date_value = str(payload.get("date", "")).strip()
        category = str(payload.get("category", "")).strip()
        handler = str(payload.get("handler", "")).strip()
        mode = str(payload.get("mode", "快速记账")).strip() or "快速记账"
        if not date_value or not category:
            raise ValueError("日期和支出类别不能为空")
        amount_source = payload.get("amountYuan", payload.get("amount"))
        amount_cents = yuan_to_cents(amount_source)
        if amount_cents <= 0:
            raise ValueError("金额必须大于 0")
        with self.database.lock, self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            new_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM expenses_v6").fetchone()[0])
            product_id = payload.get("productId")
            unit_price = payload.get("priceYuan", payload.get("price"))
            known = ("id", "date", "mode", "category", "item", "amount", "amountYuan", "handler", "status", "note", "purchaseNo", "productId", "qty", "unit", "price", "priceYuan", "importBatchId")
            conn.execute(
                """INSERT INTO expenses_v6(id,uid,expense_date,mode,category_id,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,product_name_snapshot,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id, _uid("expense", new_id, str(new_id)), date_value, mode,
                    self._category_id(conn, category), category, str(payload.get("item") or payload.get("note") or category),
                    amount_cents, handler, str(payload.get("status", "有效")), str(payload.get("note", "")), payload.get("purchaseNo"),
                    product_id, self._product_name(conn, product_id), payload.get("qty"), payload.get("unit"),
                    None if unit_price in (None, "") else yuan_to_cents(unit_price), payload.get("importBatchId"), _json_extra(payload, known),
                ),
            )
            row = conn.execute(
                "SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json FROM expenses_v6 WHERE id=?",
                (new_id,),
            ).fetchone()
            item = _expense_from_row(row)
            _audit(conn, "expense.create", {"id": new_id})
            conn.commit()
            return item

    def update_expense(self, expense_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self.database.lock, self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json FROM expenses_v6 WHERE id=?",
                (int(expense_id),),
            ).fetchone()
            if not current:
                raise ValueError("支出记录不存在")
            old = _expense_from_row(current)
            merged = {**old, **patch}
            category = str(merged.get("category", "")).strip()
            amount_source = patch.get("amountYuan", merged.get("amount"))
            price_source = patch.get("priceYuan", merged.get("price"))
            product_id = merged.get("productId")
            conn.execute(
                """UPDATE expenses_v6 SET expense_date=?,mode=?,category_id=?,category_name_snapshot=?,item=?,amount_cents=?,handler=?,status=?,note=?,purchase_no=?,product_id=?,product_name_snapshot=?,quantity=?,unit_snapshot=?,unit_price_cents=?,import_batch_id=? WHERE id=?""",
                (
                    str(merged.get("date", "")), str(merged.get("mode", "")), self._category_id(conn, category), category,
                    str(merged.get("item", "")), yuan_to_cents(amount_source), str(merged.get("handler", "")), str(merged.get("status", "有效")),
                    str(merged.get("note", "")), merged.get("purchaseNo"), product_id, self._product_name(conn, product_id), merged.get("qty"), merged.get("unit"),
                    None if price_source in (None, "") else yuan_to_cents(price_source), merged.get("importBatchId"), int(expense_id),
                ),
            )
            row = conn.execute(
                "SELECT id,expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_id,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json FROM expenses_v6 WHERE id=?",
                (int(expense_id),),
            ).fetchone()
            item = _expense_from_row(row)
            _audit(conn, "expense.update", {"id": int(expense_id)})
            conn.commit()
            return item

    def void_expense(self, expense_id: int) -> Dict[str, Any]:
        return self.update_expense(expense_id, {"status": "已作废"})

    def list_products(self, query: str = "", active: Optional[bool] = None, limit: int = 500) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        values: List[Any] = []
        if query.strip():
            clauses.append("LOWER(name || ' ' || category_name_snapshot || ' ' || brand || ' ' || spec || ' ' || unit) LIKE ?")
            values.append(f"%{query.strip().lower()}%")
        if active is not None:
            clauses.append("active=?")
            values.append(int(bool(active)))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = "SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json FROM products_v6" + where + " ORDER BY active DESC,name,id LIMIT ?"
        with self.database.lock, self.database.connect() as conn:
            rows = conn.execute(sql, [*values, min(2000, max(1, int(limit or 500)))]).fetchall()
        return [_product_from_row(row) for row in rows]

    def upsert_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        unit = str(payload.get("unit", "")).strip()
        if not name or not unit:
            raise ValueError("商品名称和单位不能为空")
        with self.database.lock, self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            product_id = int(payload.get("id") or 0)
            exists = conn.execute("SELECT 1 FROM products_v6 WHERE id=?", (product_id,)).fetchone() if product_id else None
            if not exists:
                product_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM products_v6").fetchone()[0])
            created_at = str(payload.get("createdAt") or datetime.now().date().isoformat())
            known = ("id", "name", "category", "brand", "spec", "unit", "stocktake", "reminder", "active", "createdAt")
            values = (
                product_id, _uid("product", product_id, str(product_id)), name, str(payload.get("category", "")), str(payload.get("brand", "")),
                str(payload.get("spec", "")), unit, int(bool(payload.get("stocktake", False))), int(bool(payload.get("reminder", False))),
                int(bool(payload.get("active", True))), created_at, _json_extra(payload, known),
            )
            if exists:
                conn.execute(
                    """UPDATE products_v6 SET name=?,category_name_snapshot=?,brand=?,spec=?,unit=?,stocktake_enabled=?,reminder_enabled=?,active=?,created_at=?,legacy_json=? WHERE id=?""",
                    (values[2], values[3], values[4], values[5], values[6], values[7], values[8], values[9], values[10], values[11], product_id),
                )
                event = "product.update"
            else:
                conn.execute(
                    """INSERT INTO products_v6(id,uid,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    values,
                )
                event = "product.create"
            row = conn.execute(
                "SELECT id,name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at,legacy_json FROM products_v6 WHERE id=?",
                (product_id,),
            ).fetchone()
            item = _product_from_row(row)
            _audit(conn, event, {"id": product_id})
            conn.commit()
            return item

    def list_income(self, start: str = "", end: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        values: List[Any] = []
        if start:
            clauses.append("record_date>=?")
            values.append(start)
        if end:
            clauses.append("record_date<=?")
            values.append(end)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = "SELECT id,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json FROM income_records_v6" + where + " ORDER BY record_date DESC,id DESC LIMIT ?"
        with self.database.lock, self.database.connect() as conn:
            rows = conn.execute(sql, [*values, min(5000, max(1, int(limit or 1000)))]).fetchall()
        return [_income_from_row(row) for row in rows]

    def upsert_income(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        date_value = str(payload.get("date", "")).strip()
        mode = "period" if payload.get("entryMode") == "period" else "day"
        period_start = str(payload.get("periodStart") or date_value)
        period_end = str(payload.get("periodEnd") or date_value)
        if not date_value or (mode == "period" and period_start > period_end):
            raise ValueError("收入日期或周期不正确")
        with self.database.lock, self.database.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            income_id = int(payload.get("id") or 0)
            existing = conn.execute("SELECT id FROM income_records_v6 WHERE id=?", (income_id,)).fetchone() if income_id else None
            if not existing:
                if mode == "day":
                    existing = conn.execute("SELECT id FROM income_records_v6 WHERE entry_mode='day' AND record_date=? ORDER BY id LIMIT 1", (date_value,)).fetchone()
                else:
                    existing = conn.execute("SELECT id FROM income_records_v6 WHERE entry_mode='period' AND period_start=? AND period_end=? ORDER BY id LIMIT 1", (period_start, period_end)).fetchone()
                income_id = int(existing[0]) if existing else int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM income_records_v6").fetchone()[0])
            hall = payload.get("hall")
            room = payload.get("room")
            dine_in = payload.get("dineIn", (float(hall or 0) + float(room or 0)))
            known = ("id", "date", "entryMode", "periodStart", "periodEnd", "dineIn", "hall", "room", "chess", "delivery", "note")
            values = (
                income_id, _uid("income", income_id, str(income_id)), date_value, mode, period_start, period_end, yuan_to_cents(dine_in),
                None if hall is None else yuan_to_cents(hall), None if room is None else yuan_to_cents(room), yuan_to_cents(payload.get("chess", 0)),
                yuan_to_cents(payload.get("delivery", 0)), str(payload.get("note", "")), _json_extra(payload, known),
            )
            if existing:
                conn.execute(
                    """UPDATE income_records_v6 SET record_date=?,entry_mode=?,period_start=?,period_end=?,dine_in_cents=?,hall_cents=?,room_cents=?,chess_cents=?,delivery_cents=?,note=?,legacy_json=? WHERE id=?""",
                    (values[2], values[3], values[4], values[5], values[6], values[7], values[8], values[9], values[10], values[11], values[12], income_id),
                )
                event = "income.update"
            else:
                conn.execute(
                    """INSERT INTO income_records_v6(id,uid,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    values,
                )
                event = "income.create"
            row = conn.execute(
                "SELECT id,record_date,entry_mode,period_start,period_end,dine_in_cents,hall_cents,room_cents,chess_cents,delivery_cents,note,legacy_json FROM income_records_v6 WHERE id=?",
                (income_id,),
            ).fetchone()
            item = _income_from_row(row)
            _audit(conn, event, {"id": income_id})
            conn.commit()
            return item

    def dashboard_summary(self, today: str, month_start: str, month_end: str) -> Dict[str, Any]:
        with self.database.lock, self.database.connect() as conn:
            expense_today = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date=? AND status='有效'", (today,)).fetchone()[0])
            expense_month = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date BETWEEN ? AND ? AND status='有效'", (month_start, month_end)).fetchone()[0])
            income_today = int(conn.execute("SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date=?", (today,)).fetchone()[0])
            income_month = int(conn.execute("SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date BETWEEN ? AND ?", (month_start, month_end)).fetchone()[0])
        return {
            "todayIncome": cents_to_legacy_number(income_today),
            "todayExpense": cents_to_legacy_number(expense_today),
            "monthIncome": cents_to_legacy_number(income_month),
            "monthExpense": cents_to_legacy_number(expense_month),
            "monthBalance": cents_to_legacy_number(income_month - expense_month),
        }
