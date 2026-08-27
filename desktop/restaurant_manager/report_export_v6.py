from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

from .reporting_v6 import ReportRepositoryV6
from .repositories_v6 import V6Repository


REPORT_HEADERS = {
    "expense": ("日期", "方式", "类别", "项目", "金额", "经手人", "状态", "备注"),
    "income": ("记账日期", "录入方式", "周期开始", "周期结束", "堂食", "棋牌房", "外送", "合计", "备注"),
    "sales": ("日期", "分类", "数量", "金额"),
    "stock": ("日期", "类型", "商品", "上次", "本次", "单位", "变化", "备注"),
    "price": ("日期", "商品", "数量", "单位", "单价", "小计", "经手人"),
}


def _row(kind: str, item: Dict[str, Any], product: Dict[str, Any] | None = None) -> Sequence[Any]:
    if kind == "expense":
        return (item.get("date"), item.get("mode"), item.get("category"), item.get("item"), item.get("amount"), item.get("handler"), item.get("status"), item.get("note", ""))
    if kind == "income":
        return (item.get("date"), "按周期" if item.get("entryMode") == "period" else "按日", item.get("periodStart"), item.get("periodEnd"), item.get("dineIn"), item.get("chess"), item.get("delivery"), item.get("total"), item.get("note", ""))
    if kind == "sales":
        return (item.get("date"), item.get("category"), item.get("qty"), item.get("amount"))
    if kind == "stock":
        return (item.get("date"), item.get("kind"), item.get("product"), item.get("previous"), item.get("actual"), item.get("unit"), item.get("change"), item.get("note", ""))
    return (item.get("date"), (product or {}).get("name", ""), item.get("qty"), item.get("unit"), item.get("price"), item.get("amount"), item.get("handler"))


def export_report_csv_v6(database: Any, target: Path, kind: str, query: Dict[str, Any]) -> Path:
    if kind not in REPORT_HEADERS:
        raise ValueError("不支持的查询导出类型")
    target.parent.mkdir(parents=True, exist_ok=True)
    reports = ReportRepositoryV6(database)
    page = 1
    page_size = 200
    product: Dict[str, Any] | None = None

    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_HEADERS[kind])
        while True:
            common = {
                "start": str(query.get("start", "")),
                "end": str(query.get("end", "")),
                "keyword": str(query.get("keyword", "")),
                "sort_by": str(query.get("sortBy", "date")),
                "sort_order": str(query.get("sortOrder", "desc")),
                "page": page,
                "page_size": page_size,
            }
            if kind == "expense":
                result = V6Repository(database).list_expenses(
                    start=common["start"], end=common["end"], category=str(query.get("category", "")), handler=str(query.get("handler", "")),
                    status=str(query.get("status", "有效")), keyword=common["keyword"], sort_by=common["sort_by"], sort_order=common["sort_order"],
                    page=page, page_size=page_size,
                )
            elif kind == "income":
                result = reports.income(**common)
            elif kind == "sales":
                result = reports.sales(**common)
            elif kind == "stock":
                result = reports.stock(**common)
            else:
                common.pop("keyword", None)
                result = reports.prices(product_id=int(query.get("productId", 0)), **common)
                product = result.get("product")
            for item in result.get("items", []):
                writer.writerow(_row(kind, item, product))
            if page >= int(result.get("totalPages", 1)):
                break
            page += 1
    return target
