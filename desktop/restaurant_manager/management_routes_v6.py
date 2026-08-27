from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any, Callable

from .management_v6 import (
    create_reminder_v6,
    delete_reminder_v6,
    finish_reminder_v6,
    generate_payroll_v6,
    get_payroll_v6,
    list_employees_v6,
    list_reminders_v6,
    list_suppliers_v6,
    save_payroll_v6,
    save_stocktake_v6,
    stocktake_form_v6,
    upsert_employee_v6,
    upsert_supplier_v6,
)
from .server import ApiHandler

_INSTALLED = False


def _one(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return str(values[0]) if values else default


def install_management_routes_v6() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    original_get: Callable[[ApiHandler], Any] = ApiHandler.do_GET
    original_post: Callable[[ApiHandler], Any] = ApiHandler.do_POST

    def do_get(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        paths = {
            "/api/v2/stocktake/form",
            "/api/v2/reminders",
            "/api/v2/employees",
            "/api/v2/payroll",
            "/api/v2/suppliers",
        }
        if parsed.path not in paths:
            return original_get(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if parsed.path == "/api/v2/stocktake/form":
                return self._json({"ok": True, **stocktake_form_v6(self.service.database, _one(query, "date"), _one(query, "kind", "月底盘点"))})
            if parsed.path == "/api/v2/reminders":
                return self._json({"ok": True, **list_reminders_v6(self.service.database)})
            if parsed.path == "/api/v2/employees":
                return self._json({"ok": True, "items": list_employees_v6(self.service.database)})
            if parsed.path == "/api/v2/payroll":
                return self._json({"ok": True, **get_payroll_v6(self.service.database, _one(query, "month"))})
            return self._json({"ok": True, "items": list_suppliers_v6(self.service.database)})
        except Exception as error:
            return self._api_error(error)

    def do_post(self: ApiHandler) -> Any:
        parsed = urllib.parse.urlparse(self.path)
        paths = {
            "/api/v2/stocktake/save",
            "/api/v2/reminders/create",
            "/api/v2/reminders/finish",
            "/api/v2/reminders/delete",
            "/api/v2/employees/upsert",
            "/api/v2/payroll/generate",
            "/api/v2/payroll/save",
            "/api/v2/suppliers/upsert",
        }
        if parsed.path not in paths:
            return original_post(self)
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if parsed.path == "/api/v2/stocktake/save":
                return self._json({"ok": True, "item": save_stocktake_v6(self.service.database, body)})
            if parsed.path == "/api/v2/reminders/create":
                return self._json({"ok": True, "item": create_reminder_v6(self.service.database, body)})
            if parsed.path == "/api/v2/reminders/finish":
                return self._json({"ok": True, "item": finish_reminder_v6(self.service.database, int(body.get("id", 0)))})
            if parsed.path == "/api/v2/reminders/delete":
                delete_reminder_v6(self.service.database, int(body.get("id", 0)))
                return self._json({"ok": True})
            if parsed.path == "/api/v2/employees/upsert":
                return self._json({"ok": True, "item": upsert_employee_v6(self.service.database, body)})
            if parsed.path == "/api/v2/payroll/generate":
                return self._json({"ok": True, "item": generate_payroll_v6(self.service.database, str(body.get("month", "")))})
            if parsed.path == "/api/v2/payroll/save":
                return self._json({"ok": True, "item": save_payroll_v6(self.service.database, body)})
            return self._json({"ok": True, "item": upsert_supplier_v6(self.service.database, body)})
        except Exception as error:
            return self._api_error(error)

    ApiHandler.do_GET = do_get  # type: ignore[method-assign]
    ApiHandler.do_POST = do_post  # type: ignore[method-assign]
