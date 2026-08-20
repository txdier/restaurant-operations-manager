from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from .migration_package import export_migration_package, import_migration_package, inspect_migration_package
from .server import ApiHandler, windows_dialog

_INSTALLED = False


def install_migration_routes() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_post(self: ApiHandler) -> Any:
        if not self.path.startswith("/api/migration/"):
            return original(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if self.path == "/api/migration/export":
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                    "$d.Title='导出餐馆系统迁移包';"
                    "$d.Filter='系统迁移包 (*.zip)|*.zip';$d.DefaultExt='zip';$d.AddExtension=$true;"
                    f"$d.FileName='餐馆系统迁移包_{stamp}.zip';"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                if not selected:
                    return self._json({"ok": True, "path": "", "cancelled": True})
                target = Path(selected)
                manifest = export_migration_package(self.service.database, target)
                return self._json({"ok": True, "path": str(target), "manifest": manifest})
            if self.path == "/api/migration/select":
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.OpenFileDialog;"
                    "$d.Title='选择餐馆系统迁移包';"
                    "$d.Filter='系统迁移包 (*.zip)|*.zip';$d.Multiselect=$false;"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                return self._json({"ok": True, "path": selected})
            if self.path == "/api/migration/inspect":
                source = Path(str(body.get("path", "")))
                return self._json({"ok": True, "manifest": inspect_migration_package(source)})
            if self.path == "/api/migration/import":
                source = Path(str(body.get("path", "")))
                result = import_migration_package(self.service.database, source, self.service._backup_dir())
                return self._json({"ok": True, **result, "state": self._public_state(self.service.database.load())})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
