from __future__ import annotations

import os
import sys
import logging

from .paths import data_dir, log_file
from .server import start_server
from .migration_routes import install_migration_routes
from .core_data_routes import install_core_data_routes
from .entry_routes_v6 import install_entry_routes_v6
from .operations_routes_v6 import install_operations_routes_v6
from .storage_export_routes_v6 import install_storage_export_routes
from .import_routes_v6 import install_import_routes_v6
from .report_routes_v6 import install_report_routes_v6
from .report_export_routes_v6 import install_report_export_routes_v6
from .version import APP_NAME, APP_VERSION


def configure_logging() -> None:
    target = log_file()
    handler = logging.FileHandler(str(target), encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[handler],
    )


def compatibility_environment() -> None:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    required = "--disable-features=RendererCodeIntegrity --disable-gpu --disable-gpu-compositing"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{flags} {required}".strip()
    os.environ.setdefault("QT_OPENGL", "software")


def main() -> int:
    configure_logging()
    compatibility_environment()
    install_migration_routes()
    install_core_data_routes()
    install_entry_routes_v6()
    install_operations_routes_v6()
    install_storage_export_routes()
    install_import_routes_v6()
    install_report_routes_v6()
    install_report_export_routes_v6()
    logging.info("Starting %s %s", APP_NAME, APP_VERSION)
    from PyQt5.QtCore import QUrl
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
    from PyQt5.QtWidgets import QApplication, QMainWindow

    class DiagnosticPage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):  # type: ignore[no-untyped-def]
            logging.error("JavaScript console [%s] %s:%s %s", level, source, line, message)
            super().javaScriptConsoleMessage(level, message, line, source)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    server, url = start_server()
    branding_settings = server.service.database.load().get("settings", {})
    display_name = str(branding_settings.get("appName") or APP_NAME).strip() or APP_NAME
    window_title = str(branding_settings.get("windowTitle") or display_name).strip() or display_name
    app.setApplicationDisplayName(display_name)
    window = QMainWindow()
    window.setWindowTitle(window_title)
    custom_icon = data_dir() / "branding" / "desktop-icon.ico"
    if custom_icon.exists():
        app.setWindowIcon(QIcon(str(custom_icon)))
        window.setWindowIcon(QIcon(str(custom_icon)))
    window.resize(1440, 900)
    window.setMinimumSize(1024, 700)
    view = QWebEngineView(window)
    view.setPage(DiagnosticPage(view))
    view.loadStarted.connect(lambda: logging.info("Desktop UI load started: %s", url))
    view.loadProgress.connect(lambda progress: logging.info("Desktop UI load progress: %s%%", progress))
    view.loadFinished.connect(lambda ok: logging.info("Desktop UI load finished: success=%s url=%s", ok, view.url().toString()))
    view.titleChanged.connect(window.setWindowTitle)
    view.setUrl(QUrl(url))
    window.setCentralWidget(view)
    window.show()
    def sync_branding() -> None:
        try:
            result = server.service.sync_desktop_shortcut()
            if result.get("icon"):
                icon = QIcon(str(result["icon"]))
                app.setWindowIcon(icon)
                window.setWindowIcon(icon)
        except Exception:
            logging.exception("Could not synchronize the customized desktop shortcut")

    QTimer.singleShot(1500, sync_branding)
    backup_timer = QTimer(window)
    backup_timer.timeout.connect(server.service.maybe_auto_backup)
    backup_timer.start(60_000)
    code = app.exec_()
    server.shutdown()
    server.server_close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())