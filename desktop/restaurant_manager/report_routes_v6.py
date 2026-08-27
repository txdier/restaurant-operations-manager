from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any, Callable

from .reporting_v6 import ReportRepositoryV6
from .repositories_v6 import V6Repository
from .server import ApiHandler

_INSTALLED = False


def _one(query: dict[str, list[str]], name: str, default: str = "") -> str:
    values = query.get(name)
    return str(values[0]) if values else default


def _common(query: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "start": _one(query, "start"),
        "end": _one(query, "end"),
        "keyword": _one(query, "keyword"),
        "sort_by": _one(query, "sortBy", "date"),
        "sort_order": _one(query, "sortOrder", "desc"),
        "page": int(_one(query, "page", "1")),
        "page_size": int(_one(query, "pageSize", "20")),
    }


def install_report_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/v2/reports/"):
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            reports = ReportRepositoryV6(self.service.database)
            if parsed.path == "/api/v2/reports/summary":
                return self._json({"ok": True, **reports.summary(_one(query, "start"), _one(query, "end"))})
            if parsed.path == "/api/v2/reports/options":
                return self._json({"ok": True, **reports.filter_options()})
            if parsed.path == "/api/v2/reports/expenses":
                result = V6Repository(self.service.database).list_expenses(
                    start=_one(query, "start"), end=_one(query, "end"), category=_one(query, "category"), handler=_one(query, "handler"),
                    status=_one(query, "status", "有效"), keyword=_one(query, "keyword"), sort_by=_one(query, "sortBy", "date"),
                    sort_order=_one(query, "sortOrder", "desc"), page=int(_one(query, "page", "1")), page_size=int(_one(query, "pageSize", "20")),
                )
                return self._json({"ok": True, **result})
            if parsed.path == "/api/v2/reports/income":
                return self._json({"ok": True, **reports.income(**_common(query))})
            if parsed.path == "/api/v2/reports/sales":
                return self._json({"ok": True, **reports.sales(**_common(query))})
            if parsed.path == "/api/v2/reports/stock":
                return self._json({"ok": True, **reports.stock(**_common(query))})
            if parsed.path == "/api/v2/reports/prices":
                common = _common(query)
                common.pop("keyword", None)
                return self._json({"ok": True, **reports.prices(product_id=int(_one(query, "productId", "0")), **common)})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
