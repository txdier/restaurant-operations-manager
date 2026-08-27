from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List
from uuid import uuid4

from .money import cents_to_legacy_number, yuan_to_cents
from .storage_v6 import _uid


def _amount_cents(quantity: Any, unit_price_cents: int) -> int:
    value = Decimal(str(quantity)) * Decimal(int(unit_price_cents))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def create_purchase_v6(database: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    record_date = str(payload.get("date", "")).strip()
    handler = str(payload.get("handler", "")).strip()
    note = str(payload.get("note", "")).strip()
    lines = payload.get("lines")
    if not record_date:
        raise ValueError("采购日期不能为空")
    if not handler:
        raise ValueError("经手人不能为空")
    if not isinstance(lines, list) or not lines:
        raise ValueError("请至少添加一行采购商品")

    with database.lock, database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        products: Dict[int, Dict[str, Any]] = {}
        normalized: List[Dict[str, Any]] = []
        for index, line in enumerate(lines, 1):
            product_id = int(line.get("productId") or 0)
            row = conn.execute(
                "SELECT id,name,category_name_snapshot,unit,active FROM products_v6 WHERE id=?",
                (product_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"第 {index} 行商品不存在，请重新选择")
            if not bool(row[4]):
                raise ValueError(f"第 {index} 行商品“{row[1]}”已停用，不能继续采购")
            quantity = Decimal(str(line.get("qty", 0)))
            if quantity <= 0:
                raise ValueError(f"第 {index} 行数量必须大于 0")
            unit_price_cents = yuan_to_cents(line.get("priceYuan", line.get("price", 0)))
            if unit_price_cents <= 0:
                raise ValueError(f"第 {index} 行单价必须大于 0")
            products[product_id] = {"name": str(row[1]), "category": str(row[2]), "unit": str(row[3])}
            normalized.append({
                "productId": product_id,
                "qty": float(quantity),
                "priceCents": unit_price_cents,
                "amountCents": _amount_cents(quantity, unit_price_cents),
            })

        purchase_no = str(payload.get("purchaseNo", "")).strip()
        if not purchase_no:
            purchase_no = f"CG-{record_date.replace('-', '')}-{uuid4().hex[:6].upper()}"
        exists = conn.execute("SELECT 1 FROM expenses_v6 WHERE purchase_no=? LIMIT 1", (purchase_no,)).fetchone()
        if exists:
            raise ValueError(f"采购单号“{purchase_no}”已存在")

        next_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM expenses_v6").fetchone()[0])
        category_ids = {str(name): int(category_id) for category_id, name in conn.execute("SELECT id,name FROM expense_categories_v6")}
        created: List[Dict[str, Any]] = []
        for offset, line in enumerate(normalized):
            product = products[line["productId"]]
            expense_id = next_id + offset
            item = f'{product["name"]} {line["qty"]:g}{product["unit"]}'
            conn.execute(
                """INSERT INTO expenses_v6(
                    id,uid,expense_date,mode,category_id,category_name_snapshot,item,amount_cents,handler,status,note,
                    purchase_no,product_id,product_name_snapshot,quantity,unit_snapshot,unit_price_cents,import_batch_id,legacy_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    expense_id, _uid("expense", expense_id, str(expense_id)), record_date, "详细采购",
                    category_ids.get(product["category"]), product["category"], item, line["amountCents"], handler, "有效", note,
                    purchase_no, line["productId"], product["name"], line["qty"], product["unit"], line["priceCents"], None, "",
                ),
            )
            created.append({
                "id": expense_id,
                "date": record_date,
                "mode": "详细采购",
                "category": product["category"],
                "item": item,
                "amount": cents_to_legacy_number(line["amountCents"]),
                "handler": handler,
                "status": "有效",
                "note": note,
                "purchaseNo": purchase_no,
                "productId": line["productId"],
                "qty": line["qty"],
                "unit": product["unit"],
                "price": cents_to_legacy_number(line["priceCents"]),
            })

        conn.execute(
            "INSERT INTO audit_log(event,detail) VALUES(?,?)",
            ("purchase.create", json.dumps({"purchaseNo": purchase_no, "lineCount": len(created)}, ensure_ascii=False, separators=(",", ":"))),
        )
        conn.commit()
        return {
            "purchaseNo": purchase_no,
            "items": created,
            "lineCount": len(created),
            "amount": cents_to_legacy_number(sum(int(line["amountCents"]) for line in normalized)),
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
