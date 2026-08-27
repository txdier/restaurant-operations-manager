from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .money import cents_to_legacy_number


SORTS = {
    "income": {
        "date": "record_date", "entryMode": "entry_mode", "dineIn": "dine_in_cents", "chess": "chess_cents",
        "delivery": "delivery_cents", "total": "(dine_in_cents+chess_cents+delivery_cents)", "id": "id",
    },
    "sales": {"date": "r.sale_date", "category": "l.category_name_snapshot", "qty": "l.quantity", "amount": "l.amount_cents", "id": "l.id"},
    "stock": {"date": "s.stocktake_date", "kind": "s.kind", "product": "l.product_name_snapshot", "previous": "l.previous_quantity", "actual": "l.actual_quantity", "change": "l.change_quantity", "id": "l.id"},
    "price": {"date": "e.expense_date", "qty": "e.quantity", "price": "e.unit_price_cents", "amount": "e.amount_cents", "handler": "e.handler", "id": "e.id"},
}


def _paging(page: int, page_size: int) -> tuple[int, int, int]:
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    return page, page_size, (page - 1) * page_size


def _order(kind: str, sort_by: str, sort_order: str) -> str:
    column = SORTS[kind].get(sort_by, SORTS[kind]["date"])
    direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    return f"{column} {direction}, {SORTS[kind]['id']} {direction}"


def _page_result(items: List[Dict[str, Any]], total: int, page: int, page_size: int) -> Dict[str, Any]:
    return {"items": items, "total": total, "page": page, "pageSize": page_size, "totalPages": max(1, (total + page_size - 1) // page_size)}


class ReportRepositoryV6:
    def __init__(self, database: Any) -> None:
        self.database = database

    def summary(self, start: str, end: str) -> Dict[str, Any]:
        with self.database.lock, self.database.connect() as conn:
            income = int(conn.execute(
                "SELECT COALESCE(SUM(dine_in_cents+chess_cents+delivery_cents),0) FROM income_records_v6 WHERE record_date BETWEEN ? AND ?",
                (start, end),
            ).fetchone()[0])
            expense = int(conn.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM expenses_v6 WHERE expense_date BETWEEN ? AND ? AND status='有效'",
                (start, end),
            ).fetchone()[0])
        return {"income": cents_to_legacy_number(income), "expense": cents_to_legacy_number(expense), "balance": cents_to_legacy_number(income - expense)}

    def filter_options(self) -> Dict[str, Any]:
        with self.database.lock, self.database.connect() as conn:
            categories = [str(row[0]) for row in conn.execute("SELECT name FROM expense_categories_v6 ORDER BY sort_order,id")]
            handlers = [str(row[0]) for row in conn.execute("SELECT DISTINCT handler FROM expenses_v6 WHERE TRIM(handler)<>'' ORDER BY handler")]
            products = [
                {"id": int(row[0]), "name": str(row[1]), "unit": str(row[2]), "active": bool(row[3])}
                for row in conn.execute("SELECT id,name,unit,active FROM products_v6 ORDER BY active DESC,name,id")
            ]
        return {"categories": categories, "handlers": handlers, "products": products}

    def income(self, *, start: str, end: str, keyword: str = "", sort_by: str = "date", sort_order: str = "desc", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        page, page_size, offset = _paging(page, page_size)
        clauses = ["record_date BETWEEN ? AND ?"]
        values: List[Any] = [start, end]
        if keyword.strip():
            clauses.append("LOWER(record_date || ' ' || entry_mode || ' ' || period_start || ' ' || period_end || ' ' || note) LIKE ?")
            values.append(f"%{keyword.strip().lower()}%")
        where = " WHERE " + " AND ".join(clauses)
        with self.database.lock, self.database.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM income_records_v6" + where, values).fetchone()[0])
            rows = conn.execute(
                "SELECT id,record_date,entry_mode,period_start,period_end,dine_in_cents,chess_cents,delivery_cents,note FROM income_records_v6" + where +
                f" ORDER BY {_order('income', sort_by, sort_order)} LIMIT ? OFFSET ?",
                [*values, page_size, offset],
            ).fetchall()
        items = [{
            "id": row[0], "date": row[1], "entryMode": row[2], "periodStart": row[3], "periodEnd": row[4],
            "dineIn": cents_to_legacy_number(row[5]), "chess": cents_to_legacy_number(row[6]), "delivery": cents_to_legacy_number(row[7]),
            "total": cents_to_legacy_number(int(row[5]) + int(row[6]) + int(row[7])), "note": row[8],
        } for row in rows]
        return _page_result(items, total, page, page_size)

    def sales(self, *, start: str, end: str, keyword: str = "", sort_by: str = "date", sort_order: str = "desc", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        page, page_size, offset = _paging(page, page_size)
        clauses = ["r.sale_date BETWEEN ? AND ?"]
        values: List[Any] = [start, end]
        if keyword.strip():
            clauses.append("LOWER(r.sale_date || ' ' || l.category_name_snapshot) LIKE ?")
            values.append(f"%{keyword.strip().lower()}%")
        where = " WHERE " + " AND ".join(clauses)
        base = " FROM sales_records_v6 r JOIN sales_lines_v6 l ON l.sales_record_id=r.id"
        with self.database.lock, self.database.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*)" + base + where, values).fetchone()[0])
            rows = conn.execute(
                "SELECT l.id,r.sale_date,l.category_id,l.category_name_snapshot,l.quantity,l.amount_cents" + base + where +
                f" ORDER BY {_order('sales', sort_by, sort_order)} LIMIT ? OFFSET ?",
                [*values, page_size, offset],
            ).fetchall()
        items = [{"id": row[0], "date": row[1], "categoryId": row[2], "category": row[3], "qty": row[4], "amount": cents_to_legacy_number(row[5])} for row in rows]
        return _page_result(items, total, page, page_size)

    def stock(self, *, start: str, end: str, keyword: str = "", sort_by: str = "date", sort_order: str = "desc", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        page, page_size, offset = _paging(page, page_size)
        clauses = ["s.stocktake_date BETWEEN ? AND ?"]
        values: List[Any] = [start, end]
        if keyword.strip():
            clauses.append("LOWER(s.stocktake_date || ' ' || s.kind || ' ' || l.product_name_snapshot || ' ' || l.note) LIKE ?")
            values.append(f"%{keyword.strip().lower()}%")
        where = " WHERE " + " AND ".join(clauses)
        base = " FROM stocktakes_v6 s JOIN stocktake_lines_v6 l ON l.stocktake_id=s.id"
        with self.database.lock, self.database.connect() as conn:
            total = int(conn.execute("SELECT COUNT(*)" + base + where, values).fetchone()[0])
            rows = conn.execute(
                "SELECT l.id,s.stocktake_date,s.kind,l.product_id,l.product_name_snapshot,l.previous_quantity,l.actual_quantity,l.unit_snapshot,l.change_quantity,l.note" + base + where +
                f" ORDER BY {_order('stock', sort_by, sort_order)} LIMIT ? OFFSET ?",
                [*values, page_size, offset],
            ).fetchall()
        items = [{"id": row[0], "date": row[1], "kind": row[2], "productId": row[3], "product": row[4], "previous": row[5], "actual": row[6], "unit": row[7], "change": row[8], "note": row[9]} for row in rows]
        return _page_result(items, total, page, page_size)

    def prices(self, *, product_id: int, start: str, end: str, sort_by: str = "date", sort_order: str = "desc", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        page, page_size, offset = _paging(page, page_size)
        with self.database.lock, self.database.connect() as conn:
            product = conn.execute("SELECT id,name,unit,active FROM products_v6 WHERE id=?", (int(product_id),)).fetchone()
            if not product:
                return {**_page_result([], 0, page, page_size), "product": None, "summary": {"min": 0, "max": 0, "latest": 0, "average": 0}}
            clauses = ["e.expense_date BETWEEN ? AND ?", "e.mode='详细采购'", "e.status='有效'", "(e.product_id=? OR (e.product_id IS NULL AND e.item LIKE ?))"]
            values: List[Any] = [start, end, int(product_id), f"{product[1]} %"]
            where = " WHERE " + " AND ".join(clauses)
            total = int(conn.execute("SELECT COUNT(*) FROM expenses_v6 e" + where, values).fetchone()[0])
            rows = conn.execute(
                "SELECT e.id,e.expense_date,e.quantity,e.unit_snapshot,e.unit_price_cents,e.amount_cents,e.handler FROM expenses_v6 e" + where +
                f" ORDER BY {_order('price', sort_by, sort_order)} LIMIT ? OFFSET ?",
                [*values, page_size, offset],
            ).fetchall()
            stats = conn.execute(
                "SELECT MIN(unit_price_cents),MAX(unit_price_cents),AVG(unit_price_cents) FROM expenses_v6 e" + where + " AND unit_price_cents IS NOT NULL",
                values,
            ).fetchone()
            latest = conn.execute(
                "SELECT unit_price_cents FROM expenses_v6 e" + where + " AND unit_price_cents IS NOT NULL ORDER BY expense_date DESC,id DESC LIMIT 1",
                values,
            ).fetchone()
        items = [{"id": row[0], "date": row[1], "qty": row[2], "unit": row[3] or product[2], "price": cents_to_legacy_number(row[4]) if row[4] is not None else 0, "amount": cents_to_legacy_number(row[5]), "handler": row[6]} for row in rows]
        summary = {
            "min": cents_to_legacy_number(int(stats[0])) if stats and stats[0] is not None else 0,
            "max": cents_to_legacy_number(int(stats[1])) if stats and stats[1] is not None else 0,
            "average": cents_to_legacy_number(int(round(float(stats[2])))) if stats and stats[2] is not None else 0,
            "latest": cents_to_legacy_number(int(latest[0])) if latest else 0,
        }
        return {**_page_result(items, total, page, page_size), "product": {"id": product[0], "name": product[1], "unit": product[2], "active": bool(product[3])}, "summary": summary}
