from __future__ import annotations

import json
import mimetypes
import os
import secrets
import subprocess
import threading
import urllib.parse
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

from .database import Database
from .exporter import export_csv_zip, export_xlsx
from .paths import data_dir, default_backup_dir, log_file, web_dir
from .security import hash_password, verify_password
from .version import APP_NAME, APP_VERSION, DATA_SCHEMA_VERSION


STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def static_content_type(path: Path) -> str:
    return STATIC_CONTENT_TYPES.get(path.suffix.lower(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")


class DesktopService:
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.token = secrets.token_urlsafe(24)

    def _backup_dir(self, state: Dict[str, Any] | None = None) -> Path:
        state = state or self.database.load()
        configured = str(state.get("settings", {}).get("backupDir", "")).strip()
        return Path(configured) if configured else default_backup_dir()

    def maybe_auto_backup(self) -> None:
        state = self.database.load()
        settings = state["settings"]
        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")
        if settings.get("lastAutoBackupDate") != today and now >= settings.get("backupTime", "08:00"):
            self.database.backup(self._backup_dir(state), "auto")
            settings["lastAutoBackupDate"] = today
            self.database.save(state, "auto_backup")
            self.prune_backups(state)

    def prune_backups(self, state: Dict[str, Any] | None = None) -> None:
        state = state or self.database.load()
        keep_days = max(7, int(state.get("settings", {}).get("backupKeepDays", 30)))
        cutoff = datetime.now() - timedelta(days=keep_days)
        for item in self._backup_dir(state).glob("restaurant_*.db"):
            if datetime.fromtimestamp(item.stat().st_mtime) < cutoff:
                item.unlink(missing_ok=True)

    def backup_list(self) -> list[Dict[str, Any]]:
        root = self._backup_dir()
        if not root.exists():
            return []
        result = []
        for item in sorted(root.glob("restaurant_*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = item.stat()
            result.append({
                "name": item.name,
                "path": str(item),
                "time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "kind": "自动" if "_auto" in item.name else "手动" if "_manual" in item.name else "系统保护",
                "size": stat.st_size,
            })
        return result

    def change_password(self, current: str, new: str) -> None:
        state = self.database.load()
        encoded = state.get("settings", {}).get("passwordHash", "")
        if encoded and not verify_password(current, encoded):
            raise ValueError("当前密码不正确")
        state["settings"]["passwordHash"] = hash_password(new)
        self.database.save(state, "change_password")

    def unlock(self, password: str) -> bool:
        encoded = self.database.load().get("settings", {}).get("passwordHash", "")
        return not encoded or verify_password(password, encoded)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "RestaurantManager/1.0"

    @property
    def service(self) -> DesktopService:
        return self.server.service  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def _authorized(self) -> bool:
        return self.headers.get("X-Restaurant-Token") == self.service.token

    def _json(self, value: Any, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> Dict[str, Any]:
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size) or b"{}")

    def _api_error(self, error: Exception) -> None:
        self._json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)

    def _public_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        visible = json.loads(json.dumps(state))
        visible.get("settings", {}).pop("passwordHash", None)
        return visible

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if not self._authorized():
                return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            try:
                if parsed.path == "/api/state":
                    return self._json({"ok": True, "state": self._public_state(self.service.database.load())})
                if parsed.path == "/api/meta":
                    return self._json({"ok": True, "appName": APP_NAME, "version": APP_VERSION, "schemaVersion": DATA_SCHEMA_VERSION, "dataDir": str(data_dir()), "backupDir": str(self.service._backup_dir())})
                if parsed.path == "/api/backups":
                    return self._json({"ok": True, "items": self.service.backup_list()})
                return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            except Exception as error:
                return self._api_error(error)
        self._static(parsed.path)

    def do_POST(self) -> None:
        if not self._authorized():
            return self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        try:
            body = self._body()
            if self.path == "/api/state":
                state = self.service.database.save(body.get("state", {}), body.get("event", "save_state"))
                return self._json({"ok": True, "state": self._public_state(state)})
            if self.path == "/api/backup":
                target = self.service.database.backup(self.service._backup_dir(), "manual")
                self.service.prune_backups()
                return self._json({"ok": True, "path": str(target), "items": self.service.backup_list()})
            if self.path == "/api/restore":
                source = Path(str(body.get("path", "")))
                allowed = {str(item["path"]) for item in self.service.backup_list()}
                if str(source) not in allowed:
                    raise ValueError("只能恢复当前备份目录中的文件")
                self.service.database.restore(source)
                return self._json({"ok": True, "state": self._public_state(self.service.database.load())})
            if self.path == "/api/password":
                self.service.change_password(str(body.get("current", "")), str(body.get("new", "")))
                return self._json({"ok": True})
            if self.path == "/api/unlock":
                return self._json({"ok": self.service.unlock(str(body.get("password", "")))})
            if self.path == "/api/export":
                state = self.service.database.load()
                export_dir = data_dir() / "exports"
                export_dir.mkdir(exist_ok=True)
                start, end = str(body.get("start", "")), str(body.get("end", ""))
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                kind = body.get("format", "xlsx")
                target = export_dir / (f"餐馆经营数据_{stamp}.xlsx" if kind == "xlsx" else f"餐馆经营数据_{stamp}.zip")
                (export_xlsx if kind == "xlsx" else export_csv_zip)(state, target, start, end)
                return self._json({"ok": True, "path": str(target)})
            if self.path == "/api/select-directory":
                if os.name != "nt":
                    raise ValueError("目录选择窗口仅在 Windows 桌面版中可用")
                script = "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}"
                selected = subprocess.check_output(["powershell.exe", "-STA", "-NoProfile", "-Command", script], text=True, creationflags=0x08000000).strip()
                return self._json({"ok": True, "path": selected})
            if self.path == "/api/open-directory":
                requested = Path(str(body.get("path", ""))).expanduser()
                allowed_roots = [data_dir().resolve(), self.service._backup_dir().resolve()]
                resolved = requested.resolve()
                if not any(resolved == root or root in resolved.parents for root in allowed_roots):
                    raise ValueError("只能打开本系统的数据、备份或导出目录")
                resolved.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    os.startfile(str(resolved))  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", str(resolved)])
                return self._json({"ok": True})
            return self._json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self._api_error(error)

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        root = web_dir().resolve()
        target = (root / relative).resolve()
        if root not in target.parents and target != root:
            return self.send_error(HTTPStatus.FORBIDDEN)
        if not target.is_file():
            target = root / "index.html"
        if not target.is_file():
            return self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Desktop UI has not been built")
        body = target.read_bytes()
        if target.name == "index.html":
            body = body.replace(b"__DIAGNOSTIC_LOG_PATH__", json.dumps(str(log_file()), ensure_ascii=True).encode("ascii"))
        self.send_response(200)
        self.send_header("Content-Type", static_content_type(target))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, service: DesktopService) -> None:
        super().__init__(("127.0.0.1", 0), ApiHandler)
        self.service = service


def start_server(service: DesktopService | None = None) -> Tuple[LocalServer, str]:
    service = service or DesktopService()
    service.maybe_auto_backup()
    server = LocalServer(service)
    thread = threading.Thread(target=server.serve_forever, name="restaurant-local-server", daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}/?desktopToken={urllib.parse.quote(service.token)}"
