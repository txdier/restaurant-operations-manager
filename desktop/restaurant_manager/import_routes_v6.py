from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from .importer import create_import_template
from .importer_v6 import apply_import_v6, preview_import_v6, public_preview
from .server import ApiHandler, windows_dialog

_INSTALLED = False


def install_import_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_post(self: ApiHandler) -> Any:
        if not self.path.startswith("/api/v2/import/"):
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if self.path == "/api/v2/import/select":
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.OpenFileDialog;"
                    "$d.Title='选择支出导入文件';"
                    "$d.Filter='Excel 工作簿 (*.xlsx)|*.xlsx';$d.Multiselect=$false;"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                return self._json({"ok": True, "path": selected})
            if self.path == "/api/v2/import/template":
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                    "$d.Title='保存餐馆支出导入模板';"
                    "$d.Filter='Excel 工作簿 (*.xlsx)|*.xlsx';$d.DefaultExt='xlsx';$d.AddExtension=$true;"
                    "$d.FileName='餐馆支出导入模板.xlsx';"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                if not selected:
                    return self._json({"ok": True, "path": "", "cancelled": True})
                target = create_import_template(Path(selected))
                return self._json({"ok": True, "path": str(target)})
            if self.path == "/api/v2/import/preview":
                preview = preview_import_v6(Path(str(body.get("path", ""))), self.service.database)
                return self._json({"ok": True, "preview": public_preview(preview)})
            if self.path == "/api/v2/import/apply":
                source = Path(str(body.get("path", "")))
                preview = preview_import_v6(source, self.service.database)
                if preview.get("errors"):
                    raise ValueError("导入预览仍有错误，请先修正 Excel 文件")
                self.service.database.backup(self.service._backup_dir(), "before_import")
                result = apply_import_v6(
                    preview,
                    self.service.database,
                    bool(body.get("createUnknownProducts", False)),
                    bool(body.get("importDuplicateQuickExpenses", False)),
                )
                return self._json({"ok": True, "batchId": result["batchId"], "counts": preview["counts"]})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
