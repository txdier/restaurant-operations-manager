from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any, Callable

from .product_service_v6 import product_has_history_v6, replace_product_unit_v6, set_product_active_v6
from .purchase_service_v6 import create_purchase_v6
from .server import ApiHandler

_INSTALLED = False


def install_entry_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/v2/products/history-status":
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            query = urllib.parse.parse_qs(parsed.query)
            product_id = int((query.get("id") or ["0"])[0])
            return self._json({"ok": True, "hasHistory": product_has_history_v6(self.service.database, product_id)})
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in (
            "/api/v2/purchases/create",
            "/api/v2/products/active",
            "/api/v2/products/replace-unit",
        ):
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if parsed.path == "/api/v2/purchases/create":
                return self._json({"ok": True, **create_purchase_v6(self.service.database, body)})
            if parsed.path == "/api/v2/products/active":
                item = set_product_active_v6(self.service.database, int(body.get("id", 0)), bool(body.get("active", False)))
                return self._json({"ok": True, "item": item})
            result = replace_product_unit_v6(self.service.database, body)
            return self._json({"ok": True, **result})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
