from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from temcode.main_window import MainWindow
from temcode.ui.style import VS_DARK_STYLESHEET


def run() -> int:
    if sys.platform != "win32":
        print("Temcode v1 is Windows-only. Please run on Windows.")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Temcode")
    app.setOrganizationName("Temcode")
    app.setStyleSheet(VS_DARK_STYLESHEET)

    window = MainWindow()
    if window.should_start_maximized():
        window.showMaximized()
    else:
        window.show()
    return app.exec()
