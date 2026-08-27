from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any, Callable

from .configuration_v6 import (
    bootstrap_v6,
    change_password_v6,
    patch_settings_v6,
    save_expense_categories_v6,
    save_sale_categories_v6,
    security_status_v6,
    verify_unlock_v6,
)
from .server import ApiHandler

_INSTALLED = False


def install_configuration_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/v2/bootstrap", "/api/v2/security/status"):
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            if parsed.path == "/api/v2/bootstrap":
                return self._json({"ok": True, **bootstrap_v6(self.service.database)})
            return self._json({"ok": True, **security_status_v6(self.service.database)})
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        supported = {
            "/api/v2/settings",
            "/api/v2/categories/sale",
            "/api/v2/categories/expense",
            "/api/password",
            "/api/unlock",
        }
        if parsed.path not in supported:
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if parsed.path == "/api/v2/settings":
                settings = patch_settings_v6(self.service.database, dict(body.get("patch") or {}))
                return self._json({"ok": True, "settings": settings})
            if parsed.path == "/api/v2/categories/sale":
                rows = body.get("items")
                if not isinstance(rows, list):
                    raise ValueError("销售分类数据无效")
                return self._json({"ok": True, "items": save_sale_categories_v6(self.service.database, rows)})
            if parsed.path == "/api/v2/categories/expense":
                rows = body.get("items")
                if not isinstance(rows, list):
                    raise ValueError("支出分类数据无效")
                return self._json({"ok": True, "items": save_expense_categories_v6(self.service.database, rows)})
            if parsed.path == "/api/password":
                change_password_v6(self.service.database, str(body.get("current", "")), str(body.get("new", "")))
                return self._json({"ok": True, **security_status_v6(self.service.database)})
            return self._json({"ok": verify_unlock_v6(self.service.database, str(body.get("password", "")))})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
