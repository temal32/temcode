from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from temcode import __version__
from temcode.main_window import MainWindow
from temcode.ui.style import DEFAULT_THEME_ID, theme_stylesheet_for

_WINDOWS_APP_USER_MODEL_ID = "Temcode.Temcode.Editor"


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_WINDOWS_APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def _resolve_app_icon() -> QIcon | None:
    module_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(module_dir, os.pardir))
    candidate_dirs = (
        os.path.join(project_root, "assets"),
        os.path.join(module_dir, "assets"),
    )
    for assets_dir in candidate_dirs:
        for filename in ("temcode_logo.ico", "temcode_logo.png"):
            icon_path = os.path.join(assets_dir, filename)
            if os.path.isfile(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    return icon
    return None


def run() -> int:
    if sys.platform != "win32":
        print(f"Temcode v{__version__} is Windows-only. Please run on Windows.")
        return 1

    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Temcode")
    app.setOrganizationName("Temcode")
    app.setStyleSheet(theme_stylesheet_for(DEFAULT_THEME_ID))
    app_icon = _resolve_app_icon()
    if app_icon is not None:
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if app_icon is not None:
        window.setWindowIcon(app_icon)
    if window.should_start_maximized():
        window.showMaximized()
    else:
        window.show()
    return app.exec()
