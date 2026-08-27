from __future__ import annotations

import calendar
import urllib.parse
from datetime import date
from http import HTTPStatus
from typing import Any, Callable, Optional

from .repositories_v6 import V6Repository
from .server import ApiHandler

_INSTALLED = False


def _one(values: dict[str, list[str]], name: str, default: str = "") -> str:
    items = values.get(name)
    return str(items[0]) if items else default


def _optional_bool(value: str) -> Optional[bool]:
    if value == "":
        return None
    if value.lower() in ("1", "true", "yes", "on"):
        return True
    if value.lower() in ("0", "false", "no", "off"):
        return False
    raise ValueError("active 参数必须是 true/false")


def install_core_data_routes() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/v2/"):
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            repo = V6Repository(self.service.database)
            if parsed.path == "/api/v2/expenses":
                result = repo.list_expenses(
                    start=_one(query, "start"),
                    end=_one(query, "end"),
                    category=_one(query, "category"),
                    handler=_one(query, "handler"),
                    status=_one(query, "status"),
                    keyword=_one(query, "keyword"),
                    sort_by=_one(query, "sortBy", "date"),
                    sort_order=_one(query, "sortOrder", "desc"),
                    page=int(_one(query, "page", "1")),
                    page_size=int(_one(query, "pageSize", "50")),
                )
                return self._json({"ok": True, **result})
            if parsed.path == "/api/v2/expenses/recent":
                items = repo.recent_expenses(int(_one(query, "limit", "20")), _one(query, "status", "有效"))
                return self._json({"ok": True, "items": items})
            if parsed.path == "/api/v2/products":
                items = repo.list_products(
                    query=_one(query, "q"),
                    active=_optional_bool(_one(query, "active")),
                    limit=int(_one(query, "limit", "500")),
                )
                return self._json({"ok": True, "items": items})
            if parsed.path == "/api/v2/income":
                items = repo.list_income(_one(query, "start"), _one(query, "end"), int(_one(query, "limit", "1000")))
                return self._json({"ok": True, "items": items})
            if parsed.path == "/api/v2/dashboard":
                day = _one(query, "date", date.today().isoformat())
                year, month = int(day[:4]), int(day[5:7])
                month_start = f"{year:04d}-{month:02d}-01"
                month_end = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
                result = repo.dashboard_summary(day, month_start, month_end)
                return self._json({"ok": True, **result})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/v2/"):
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            repo = V6Repository(self.service.database)
            if parsed.path == "/api/v2/expenses/create":
                return self._json({"ok": True, "item": repo.create_expense(body)})
            if parsed.path == "/api/v2/expenses/update":
                return self._json({"ok": True, "item": repo.update_expense(int(body.get("id", 0)), body.get("patch", {}))})
            if parsed.path == "/api/v2/expenses/void":
                return self._json({"ok": True, "item": repo.void_expense(int(body.get("id", 0)))})
            if parsed.path == "/api/v2/products/upsert":
                return self._json({"ok": True, "item": repo.upsert_product(body)})
            if parsed.path == "/api/v2/income/upsert":
                return self._json({"ok": True, "item": repo.upsert_income(body)})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
