from __future__ import annotations

import csv
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Sequence, Tuple

from .money import cents_to_legacy_number
from .repositories_v6 import EXPENSE_SORT_COLUMNS


Dataset = Tuple[str, Sequence[str], Iterable[Sequence[Any]]]


def _date_clause(column: str, start: str, end: str) -> tuple[str, List[Any]]:
    clauses: List[str] = []
    values: List[Any] = []
    if start:
        clauses.append(f"{column}>=?")
        values.append(start)
    if end:
        clauses.append(f"{column}<=?")
        values.append(end)
    return (" WHERE " + " AND ".join(clauses) if clauses else "", values)


def _iter_query(database: Any, sql: str, params: Sequence[Any] = (), chunk_size: int = 500) -> Iterator[tuple[Any, ...]]:
    with database.lock, database.connect() as conn:
        cursor = conn.execute(sql, tuple(params))
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break
            for row in rows:
                yield tuple(row)


def _income_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    where, params = _date_clause("record_date", start, end)
    sql = (
        "SELECT record_date,entry_mode,period_start,period_end,dine_in_cents,chess_cents,delivery_cents,note "
        "FROM income_records_v6" + where + " ORDER BY record_date,id"
    )
    for row in _iter_query(database, sql, params):
        total = int(row[4]) + int(row[5]) + int(row[6])
        yield (
            row[0], "按周期" if row[1] == "period" else "按日", row[2], row[3],
            cents_to_legacy_number(row[4]), cents_to_legacy_number(row[5]), cents_to_legacy_number(row[6]),
            cents_to_legacy_number(total), row[7],
        )


def _sales_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    where, params = _date_clause("r.sale_date", start, end)
    sql = (
        "SELECT r.sale_date,l.category_name_snapshot,l.quantity,l.amount_cents "
        "FROM sales_records_v6 r JOIN sales_lines_v6 l ON l.sales_record_id=r.id" + where +
        " ORDER BY r.sale_date,r.id,l.id"
    )
    for row in _iter_query(database, sql, params):
        yield (row[0], row[1], row[2], cents_to_legacy_number(row[3]))


def _expense_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    where, params = _date_clause("e.expense_date", start, end)
    sql = (
        "SELECT e.expense_date,e.mode,e.category_name_snapshot,e.item,e.amount_cents,e.handler,e.status,e.note,e.purchase_no,"
        "e.product_name_snapshot,e.quantity,e.unit_snapshot,e.unit_price_cents,e.import_batch_id "
        "FROM expenses_v6 e" + where + " ORDER BY e.expense_date,e.id"
    )
    for row in _iter_query(database, sql, params):
        yield (
            row[0], row[1], row[2], row[3], cents_to_legacy_number(row[4]), row[5], row[6], row[7], row[8] or "", row[9] or "",
            row[10] if row[10] is not None else "", row[11] or "",
            cents_to_legacy_number(row[12]) if row[12] is not None else "", row[13] or "",
        )


def _product_rows(database: Any) -> Iterator[Sequence[Any]]:
    sql = (
        "SELECT name,category_name_snapshot,brand,spec,unit,stocktake_enabled,reminder_enabled,active,created_at "
        "FROM products_v6 ORDER BY id"
    )
    for row in _iter_query(database, sql):
        yield (row[0], row[1], row[2], row[3], row[4], "是" if row[5] else "否", "是" if row[6] else "否", "启用" if row[7] else "停用", row[8] or "")


def _stocktake_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    where, params = _date_clause("s.stocktake_date", start, end)
    sql = (
        "SELECT s.stocktake_date,s.kind,l.product_name_snapshot,l.previous_quantity,l.actual_quantity,l.unit_snapshot,l.change_quantity,l.note "
        "FROM stocktakes_v6 s JOIN stocktake_lines_v6 l ON l.stocktake_id=s.id" + where + " ORDER BY s.stocktake_date,s.id,l.id"
    )
    yield from _iter_query(database, sql, params)


def _reminder_rows(database: Any) -> Iterator[Sequence[Any]]:
    sql = "SELECT name,product_name_snapshot,next_date,cycle_days,done FROM reminders_v6 ORDER BY next_date,id"
    for row in _iter_query(database, sql):
        yield (row[0], row[1], row[2], row[3], "已完成" if row[4] else "待提醒")


def _employee_rows(database: Any) -> Iterator[Sequence[Any]]:
    sql = "SELECT name,role,standard_salary_cents,start_date,active FROM employees_v6 ORDER BY id"
    for row in _iter_query(database, sql):
        yield (row[0], row[1], cents_to_legacy_number(row[2]), row[3], "在职" if row[4] else "离职")


def _payroll_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if start:
        clauses.append("p.month>=?")
        params.append(start[:7])
    if end:
        clauses.append("p.month<=?")
        params.append(end[:7])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (
        "SELECT p.month,p.confirmed,l.employee_name_snapshot,l.role_snapshot,l.standard_salary_cents,l.actual_salary_cents,l.note "
        "FROM payrolls_v6 p JOIN payroll_lines_v6 l ON l.payroll_id=p.id" + where + " ORDER BY p.month,p.id,l.id"
    )
    for row in _iter_query(database, sql, params):
        yield (row[0], "已确认" if row[1] else "未确认", row[2], row[3], cents_to_legacy_number(row[4]), cents_to_legacy_number(row[5]), row[6])


def _supplier_rows(database: Any) -> Iterator[Sequence[Any]]:
    sql = "SELECT name,contact,phone,qualification,note,active FROM suppliers_v6 ORDER BY id"
    for row in _iter_query(database, sql):
        yield (row[0], row[1], row[2], row[3], row[4], "启用" if row[5] else "停用")


def _asset_rows(database: Any, start: str, end: str) -> Iterator[Sequence[Any]]:
    where, params = _date_clause("record_date", start, end)
    sql = "SELECT asset_type,name,quantity,unit,record_date,amount_cents,status,note FROM assets_v6" + where + " ORDER BY record_date,id"
    for row in _iter_query(database, sql, params):
        yield ("设备" if row[0] == "asset" else "装修", row[1], row[2], row[3], row[4], cents_to_legacy_number(row[5]), row[6], row[7])


def relational_datasets(database: Any, start: str = "", end: str = "") -> List[Dataset]:
    return [
        ("收入记录", ("记账日期", "录入方式", "周期开始", "周期结束", "堂食", "棋牌房", "外送", "合计", "备注"), _income_rows(database, start, end)),
        ("销售统计", ("日期", "分类", "销售数量", "销售金额"), _sales_rows(database, start, end)),
        ("支出记录", ("日期", "方式", "类别", "项目", "金额", "经手人", "状态", "备注", "采购单号", "商品", "数量", "单位", "单价", "导入批次"), _expense_rows(database, start, end)),
        ("商品档案", ("商品名称", "类别", "品牌", "规格", "单位", "参与盘点", "补货提醒", "状态", "创建日期"), _product_rows(database)),
        ("盘点记录", ("日期", "盘点类型", "商品", "上次盘点", "本次盘点", "单位", "变化", "备注"), _stocktake_rows(database, start, end)),
        ("补货提醒", ("提醒名称", "商品", "下次日期", "周期天数", "状态"), _reminder_rows(database)),
        ("员工档案", ("姓名", "岗位", "标准月薪", "入职日期", "状态"), _employee_rows(database)),
        ("工资记录", ("月份", "确认状态", "员工", "岗位", "标准月薪", "实际工资", "备注"), _payroll_rows(database, start, end)),
        ("供应商", ("名称", "联系人", "电话", "资质", "备注", "状态"), _supplier_rows(database)),
        ("装修设备", ("类型", "名称", "数量", "单位", "日期", "金额", "状态", "备注"), _asset_rows(database, start, end)),
    ]


def export_csv_zip_v6(database: Any, target: Path, start: str = "", end: str = "") -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        paths: List[Path] = []
        for name, headers, rows in relational_datasets(database, start, end):
            path = root / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row)
            paths.append(path)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.name)
    return target


def export_xlsx_v6(database: Any, target: Path, start: str = "", end: str = "") -> Path:
    from openpyxl import Workbook

    target.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook(write_only=True)
    for name, headers, rows in relational_datasets(database, start, end):
        sheet = book.create_sheet(name[:31])
        sheet.append(list(headers))
        for row in rows:
            sheet.append(list(row))
    book.save(target)
    return target


def _expense_export_filter(
    *, start: str = "", end: str = "", category: str = "", handler: str = "", status: str = "", keyword: str = "",
) -> tuple[str, List[Any]]:
    clauses: List[str] = []
    values: List[Any] = []
    if start:
        clauses.append("expense_date>=?"); values.append(start)
    if end:
        clauses.append("expense_date<=?"); values.append(end)
    if category and category != "全部类别":
        clauses.append("category_name_snapshot=?"); values.append(category)
    if handler and handler != "全部经手人":
        clauses.append("handler=?"); values.append(handler)
    if status and status != "全部":
        clauses.append("status=?"); values.append(status)
    if keyword:
        clauses.append("LOWER(item || ' ' || category_name_snapshot || ' ' || handler || ' ' || mode || ' ' || status || ' ' || note) LIKE ?")
        values.append(f"%{keyword.strip().lower()}%")
    return (" WHERE " + " AND ".join(clauses) if clauses else "", values)


def export_expense_query_csv_v6(
    database: Any,
    target: Path,
    *,
    start: str = "",
    end: str = "",
    category: str = "",
    handler: str = "",
    status: str = "",
    keyword: str = "",
    sort_by: str = "date",
    sort_order: str = "desc",
) -> Path:
    where, params = _expense_export_filter(start=start, end=end, category=category, handler=handler, status=status, keyword=keyword)
    column = EXPENSE_SORT_COLUMNS.get(sort_by, "expense_date")
    direction = "ASC" if sort_order.lower() == "asc" else "DESC"
    sql = (
        "SELECT expense_date,mode,category_name_snapshot,item,amount_cents,handler,status,note,purchase_no,product_name_snapshot,quantity,unit_snapshot,unit_price_cents "
        f"FROM expenses_v6{where} ORDER BY {column} {direction},id {direction}"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(("日期", "方式", "类别", "项目", "金额", "经手人", "状态", "备注", "采购单号", "商品", "数量", "单位", "单价"))
        for row in _iter_query(database, sql, params):
            writer.writerow((
                row[0], row[1], row[2], row[3], cents_to_legacy_number(row[4]), row[5], row[6], row[7], row[8] or "", row[9] or "",
                row[10] if row[10] is not None else "", row[11] or "", cents_to_legacy_number(row[12]) if row[12] is not None else "",
            ))
    return target
