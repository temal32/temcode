from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from temcode import __version__
from temcode.main_window import MainWindow
from temcode.ui.style import DEFAULT_THEME_ID, theme_stylesheet_for


def run() -> int:
    if sys.platform != "win32":
        print(f"Temcode v{__version__} is Windows-only. Please run on Windows.")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Temcode")
    app.setOrganizationName("Temcode")
    app.setStyleSheet(theme_stylesheet_for(DEFAULT_THEME_ID))

    window = MainWindow()
    if window.should_start_maximized():
        window.showMaximized()
    else:
        window.show()
    return app.exec()
