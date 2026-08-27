from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from .report_export_v6 import export_report_csv_v6
from .server import ApiHandler, windows_dialog

_INSTALLED = False


def install_report_export_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_post(self: ApiHandler) -> Any:
        if self.path != "/api/v2/export/report":
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            kind = str(body.get("kind", "expense"))
            names = {"expense": "支出查询结果", "income": "收入查询结果", "sales": "销售统计查询结果", "stock": "盘点查询结果", "price": "商品历史价格"}
            if kind not in names:
                raise ValueError("不支持的查询导出类型")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            selected = windows_dialog(
                "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                "$d.Title='导出查询结果';$d.Filter='CSV 文件 (*.csv)|*.csv';$d.DefaultExt='csv';$d.AddExtension=$true;"
                f"$d.FileName='{names[kind]}_{stamp}.csv';"
                "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                "$d.Dispose();$owner.Dispose()"
            )
            if not selected:
                return self._json({"ok": True, "path": "", "cancelled": True})
            target = export_report_csv_v6(self.service.database, Path(selected), kind, body)
            return self._json({"ok": True, "path": str(target)})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
