from __future__ import annotations

import urllib.parse
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from .exporter_v6 import export_csv_zip_v6, export_expense_query_csv_v6, export_xlsx_v6
from .server import ApiHandler, windows_dialog
from .storage_diagnostics_v6 import storage_status

_INSTALLED = False


def install_storage_export_routes() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/v2/storage/status", "/api/v2/storage/verify"):
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            result = storage_status(self.service.database, verify=parsed.path.endswith("/verify"))
            return self._json({"ok": True, **result})
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/v2/export/all", "/api/v2/export/expenses"):
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if parsed.path == "/api/v2/export/all":
                kind = str(body.get("format", "xlsx")).lower()
                if kind not in ("xlsx", "zip"):
                    raise ValueError("导出格式只支持 xlsx 或 zip")
                extension = "xlsx" if kind == "xlsx" else "zip"
                label = "Excel 工作簿 (*.xlsx)|*.xlsx" if kind == "xlsx" else "ZIP 压缩包 (*.zip)|*.zip"
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                    "$d.Title='导出餐馆经营数据';"
                    f"$d.Filter='{label}';$d.DefaultExt='{extension}';$d.AddExtension=$true;"
                    f"$d.FileName='餐馆经营数据_{stamp}.{extension}';"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                if not selected:
                    return self._json({"ok": True, "path": "", "cancelled": True})
                target = Path(selected)
                exporter = export_xlsx_v6 if kind == "xlsx" else export_csv_zip_v6
                exporter(self.service.database, target, str(body.get("start", "")), str(body.get("end", "")))
                return self._json({"ok": True, "path": str(target)})

            selected = windows_dialog(
                "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                "$d.Title='导出支出查询结果';"
                "$d.Filter='CSV 文件 (*.csv)|*.csv';$d.DefaultExt='csv';$d.AddExtension=$true;"
                f"$d.FileName='支出查询结果_{stamp}.csv';"
                "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                "$d.Dispose();$owner.Dispose()"
            )
            if not selected:
                return self._json({"ok": True, "path": "", "cancelled": True})
            target = export_expense_query_csv_v6(
                self.service.database,
                Path(selected),
                start=str(body.get("start", "")),
                end=str(body.get("end", "")),
                category=str(body.get("category", "")),
                handler=str(body.get("handler", "")),
                status=str(body.get("status", "")),
                keyword=str(body.get("keyword", "")),
                sort_by=str(body.get("sortBy", "date")),
                sort_order=str(body.get("sortOrder", "desc")),
            )
            return self._json({"ok": True, "path": str(target)})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
