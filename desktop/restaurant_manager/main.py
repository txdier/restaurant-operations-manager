from __future__ import annotations

import os
import sys

from .server import start_server
from .version import APP_NAME


def main() -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=RendererCodeIntegrity")
    from PyQt5.QtCore import QUrl
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWidgets import QApplication, QMainWindow

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    server, url = start_server()
    window = QMainWindow()
    window.setWindowTitle(APP_NAME)
    window.resize(1440, 900)
    window.setMinimumSize(1024, 700)
    view = QWebEngineView(window)
    view.setUrl(QUrl(url))
    window.setCentralWidget(view)
    window.show()
    backup_timer = QTimer(window)
    backup_timer.timeout.connect(server.service.maybe_auto_backup)
    backup_timer.start(60_000)
    code = app.exec_()
    server.shutdown()
    server.server_close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
