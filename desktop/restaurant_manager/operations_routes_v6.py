from __future__ import annotations

import urllib.parse
from datetime import date
from http import HTTPStatus
from typing import Any, Callable

from .operations_v6 import dashboard_detail_v6, get_sales_record_v6, save_sales_record_v6
from .server import ApiHandler

_INSTALLED = False


def install_operations_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/v2/dashboard/detail", "/api/v2/sales"):
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            day = str((query.get("date") or [date.today().isoformat()])[0])
            if parsed.path == "/api/v2/dashboard/detail":
                return self._json({"ok": True, **dashboard_detail_v6(self.service.database, day)})
            return self._json({"ok": True, **get_sales_record_v6(self.service.database, day)})
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/v2/sales/save":
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            item = save_sales_record_v6(self.service.database, self._body())
            return self._json({"ok": True, "item": item})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
