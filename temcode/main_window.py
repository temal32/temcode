from __future__ import annotations

import json
import os
import random
import shutil
import hashlib
import re
import subprocess
import time
import webbrowser
from datetime import datetime

from PySide6.QtCore import QDir, QEvent, QFileSystemWatcher, QModelIndex, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QCloseEvent, QIcon, QKeySequence, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QDockWidget,
    QFileDialog,
    QFileSystemModel,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from temcode import __version__
from temcode.editor import CodeEditor, ImageViewer, LanguageId
from temcode.lsp import LspClient, uri_to_path
from temcode.terminal import CmdTerminalWidget
from temcode.ui.style import (
    DEFAULT_THEME_ID,
    available_theme_ids,
    normalize_theme_id,
    theme_display_name,
    theme_stylesheet_for,
)


class MainWindow(QMainWindow):
    _LARGE_FILE_SIZE_THRESHOLD_BYTES = 2 * 1024 * 1024
    _LARGE_FILE_LINE_THRESHOLD = 25_000
    _FILE_WATCH_POLL_INTERVAL_MS = 2000
    _FILE_WATCH_INTERNAL_WRITE_GRACE_SECONDS = 1.5
    _DEFAULT_AUTOSAVE_ENABLED = True
    _DEFAULT_AUTOSAVE_INTERVAL_SECONDS = 20
    _MIN_AUTOSAVE_INTERVAL_SECONDS = 5
    _MAX_AUTOSAVE_INTERVAL_SECONDS = 3600
    _SETTINGS_DIR_NAME = ".temcode"
    _SETTINGS_FILE_NAME = "settings.json"
    _AUTOSAVE_DIR_NAME = "autosave"
    _RECENT_PATHS_FILE_NAME = "recent_paths.json"
    _MAX_RECENT_PATHS = 20
    _BOTTOM_LAYOUT_SIDE_BY_SIDE = "side_by_side"
    _DEFAULT_THEME_ID = DEFAULT_THEME_ID
    _DEFAULT_UI_ZOOM_PERCENT = 100
    _MIN_UI_ZOOM_PERCENT = 70
    _MAX_UI_ZOOM_PERCENT = 200
    _UI_ZOOM_STEP_PERCENT = 10
    _MIN_CODE_ZOOM_POINT_SIZE = CodeEditor._MIN_ZOOM_POINT_SIZE
    _MAX_CODE_ZOOM_POINT_SIZE = CodeEditor._MAX_ZOOM_POINT_SIZE
    _TAB_CLOSE_BUTTON_BASE_WIDTH = 24
    _TAB_CLOSE_BUTTON_BASE_HEIGHT = 20
    _MIN_WINDOW_WIDTH = 640
    _MIN_WINDOW_HEIGHT = 420
    _MIN_TERMINAL_DOCK_HEIGHT = 80
    _UI_SETTINGS_PERSIST_DEBOUNCE_MS = 250
    _GITHUB_REPO_URL = "https://github.com/temal32/temcode"
    _LSP_DID_CHANGE_DEBOUNCE_MS = 180
    _LSP_MAX_COMPLETION_ITEMS = 40
    _LSP_MAX_DIAGNOSTIC_SELECTIONS = 350
    _MAX_WORKSPACE_SEARCH_RESULTS = 1200
    _SEARCH_SNIPPET_MAX_LENGTH = 160
    _GIT_STATUS_MAX_ENTRIES = 4000
    _GIT_LOG_MAX_ENTRIES = 200
    _GIT_COMMAND_TIMEOUT_SECONDS = 120
    _GIT_DISCOVERY_MAX_DIRECTORIES = 12000
    _GIT_DISCOVERY_MAX_SECONDS = 2.5
    _GIT_REMOTE_CHECK_MIN_INTERVAL_SECONDS = 20.0
    _GIT_REMOTE_CHECK_TIMEOUT_SECONDS = 45
    _SEARCH_IGNORED_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
    }
    _WELCOME_TITLES = (
        "Welcome to Temcode, {user}",
        "What do you want to code today?",
        "Ready to build something useful?",
        "Start small, ship fast.",
        "Your next idea starts here.",
        "Write clean code and make it real.",
        "Open a file and get moving.",
        "Time to turn ideas into features.",
        "Need a fresh script? Let us begin.",
        "Pick a project and dive in.",
        "Another session, another milestone.",
        "Create, test, improve, repeat.",
        "What are we building today, {user}?",
        "One commit closer to done.",
        "Debug less, build more.",
        "Ship one thing today.",
        "Let us get this project in shape.",
        "Focus mode: on.",
        "Code with intent, {user}.",
        "New session, new progress.",
    )
    _IMAGE_FILE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".webp",
        ".tif",
        ".tiff",
        ".ico",
    }

    def __init__(self) -> None:
        super().__init__()
        self.workspace_root: str | None = None
        self._open_editors_by_path: dict[str, CodeEditor] = {}
        self._open_image_tabs_by_path: dict[str, ImageViewer] = {}
        self._untitled_counter = 1
        self._active_editor_tabs: QTabWidget | None = None
        self._find_highlight_editor: CodeEditor | None = None
        self._autosave_enabled = self._DEFAULT_AUTOSAVE_ENABLED
        self._autosave_interval_seconds = self._DEFAULT_AUTOSAVE_INTERVAL_SECONDS
        self._autosave_last_summary = ""
        self._theme_id = self._DEFAULT_THEME_ID
        self._ui_zoom_percent = self._DEFAULT_UI_ZOOM_PERCENT
        self._code_zoom_point_size: float | None = None
        self._python_interpreter_path: str | None = None
        self._settings_file_path: str | None = None
        self._recent_paths_file_path: str | None = None
        self._recent_paths: list[str] = []
        self._bottom_layout_mode = self._BOTTOM_LAYOUT_SIDE_BY_SIDE
        self._suspend_ui_settings_persistence = False
        self._settings_persistence_splitter_ids: set[int] = set()
        self._is_app_closing = False
        self._start_maximized = True
        self._startup_window_mode_loaded = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(False)
        self._autosave_timer.timeout.connect(self._run_autosave_cycle)
        self._ui_settings_persist_timer = QTimer(self)
        self._ui_settings_persist_timer.setSingleShot(True)
        self._ui_settings_persist_timer.setInterval(self._UI_SETTINGS_PERSIST_DEBOUNCE_MS)
        self._ui_settings_persist_timer.timeout.connect(self._persist_ui_settings)
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_watched_file_changed)
        self._file_watcher.directoryChanged.connect(self._on_watched_directory_changed)
        self._file_poll_timer = QTimer(self)
        self._file_poll_timer.setSingleShot(False)
        self._file_poll_timer.setInterval(self._FILE_WATCH_POLL_INTERVAL_MS)
        self._file_poll_timer.timeout.connect(self._poll_watched_files)
        self._file_disk_state: dict[str, tuple[int, int]] = {}
        self._recent_internal_writes: dict[str, float] = {}
        self._external_change_prompts: set[str] = set()
        self.terminal_console: CmdTerminalWidget | None = None
        self._lsp_client = LspClient(self)
        self._lsp_document_timers: dict[int, QTimer] = {}
        self._lsp_diagnostics_by_path: dict[str, list[dict[str, object]]] = {}
        self._lsp_ready = False
        self._lsp_status_message = "idle"
        self._solution_nav_panel = "explorer"
        self._git_known_repositories: list[str] = []
        self._git_active_repository: str | None = None
        self._git_status_entries: list[dict[str, object]] = []
        self._git_branch_summary = ""
        self._git_repo_scan_workspace: str | None = None
        self._git_last_remote_check_by_repo: dict[str, float] = {}
        self._git_remote_delta_by_repo: dict[str, tuple[int, int]] = {}
        self._git_remote_prompted_head_by_repo: dict[str, str] = {}

        self.setWindowTitle("Temcode")
        self.resize(1920, 980)

        self._build_menu_bar()
        self._build_status_bar()
        self._build_central_editor_area()
        self._build_solution_explorer_dock()
        self._build_output_dock()
        self._build_terminal_dock()
        self._connect_splitter_move_persistence_hooks()
        self.installEventFilter(self)
        self._lsp_client.ready_changed.connect(self._on_lsp_ready_changed)
        self._lsp_client.diagnostics_published.connect(self._on_lsp_diagnostics_published)
        self._lsp_client.log_message.connect(lambda message: self.log(f"[lsp] {message}"))

        self._load_workspace_settings()
        self._load_recent_paths()
        self._sync_file_watcher_paths()
        self._refresh_breadcrumbs()
        self._update_solution_explorer_surface()
        self._refresh_git_repositories(preserve_selection=False)
        self._refresh_lsp_status_label()
        self._file_poll_timer.start()
        self._apply_pointing_cursor_to_buttons(self)

    def should_start_maximized(self) -> bool:
        return self._start_maximized

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        view_menu = self.menuBar().addMenu("&View")
        code_menu = self.menuBar().addMenu("&Code")
        help_menu = self.menuBar().addMenu("&Help")

        self.new_file_action = QAction("&New File", self)
        self.new_file_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_file_action.triggered.connect(self.new_file)

        self.open_file_action = QAction("&Open File...", self)
        self.open_file_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_file_action.triggered.connect(self.open_file_dialog)

        self.open_folder_action = QAction("Open &Folder...", self)
        self.open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_folder_action.triggered.connect(self.open_folder_dialog)

        self.close_workspace_action = QAction("&Close Workspace", self)
        self.close_workspace_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self.close_workspace_action.triggered.connect(self.close_workspace)

        self.save_action = QAction("&Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_current_file)

        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.save_current_file_as)

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)

        file_menu.addAction(self.new_file_action)
        file_menu.addAction(self.open_file_action)
        file_menu.addAction(self.open_folder_action)
        file_menu.addAction(self.close_workspace_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu.addAction(QAction("&Undo", self))
        edit_menu.addAction(QAction("&Redo", self))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Cu&t", self))
        edit_menu.addAction(QAction("&Copy", self))
        edit_menu.addAction(QAction("&Paste", self))
        edit_menu.addSeparator()

        self.find_action = QAction("&Find", self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(lambda: self.open_find_panel(show_replace=False))

        self.replace_action = QAction("&Replace", self)
        self.replace_action.setShortcut(QKeySequence.StandardKey.Replace)
        self.replace_action.triggered.connect(lambda: self.open_find_panel(show_replace=True))

        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.replace_action)
        edit_menu.addSeparator()

        self.settings_action = QAction("&Settings...", self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(self.open_settings_dialog)
        edit_menu.addAction(self.settings_action)

        self.trigger_completion_action = QAction("Trigger Completion", self)
        self.trigger_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.trigger_completion_action.triggered.connect(self.trigger_lsp_completion)

        self.go_to_definition_action = QAction("Go To Definition", self)
        self.go_to_definition_action.setShortcut(QKeySequence("F12"))
        self.go_to_definition_action.triggered.connect(self.go_to_definition)

        self.rename_symbol_action = QAction("Rename Symbol", self)
        self.rename_symbol_action.setShortcut(QKeySequence("F2"))
        self.rename_symbol_action.triggered.connect(self.rename_symbol)

        code_menu.addAction(self.trigger_completion_action)
        code_menu.addAction(self.go_to_definition_action)
        code_menu.addAction(self.rename_symbol_action)

        self.solution_explorer_toggle_action = QAction("Explorer", self)
        self.output_toggle_action = QAction("Output", self)
        self.terminal_toggle_action = QAction("Terminal", self)
        self.split_toggle_action = QAction("Split Editor", self)
        self.split_toggle_action.setCheckable(True)
        self.split_toggle_action.toggled.connect(self._set_split_enabled)
        self.move_tab_to_other_split_action = QAction("Move Tab To Other Split", self)
        self.move_tab_to_other_split_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.move_tab_to_other_split_action.triggered.connect(self.move_current_tab_to_other_split)

        self.zoom_in_ui_action = QAction("Zoom In", self)
        self.zoom_in_ui_action.setShortcut(QKeySequence("Ctrl+="))
        self.zoom_in_ui_action.triggered.connect(lambda: self._adjust_ui_zoom(1))

        self.zoom_out_ui_action = QAction("Zoom Out", self)
        self.zoom_out_ui_action.setShortcut(QKeySequence("Ctrl+-"))
        self.zoom_out_ui_action.triggered.connect(lambda: self._adjust_ui_zoom(-1))

        self.zoom_reset_ui_action = QAction("Reset Zoom", self)
        self.zoom_reset_ui_action.setShortcut(QKeySequence("Ctrl+0"))
        self.zoom_reset_ui_action.triggered.connect(self._reset_ui_zoom)

        view_menu.addAction(self.solution_explorer_toggle_action)
        view_menu.addAction(self.output_toggle_action)
        view_menu.addAction(self.terminal_toggle_action)
        view_menu.addSeparator()
        view_menu.addAction(self.split_toggle_action)
        view_menu.addAction(self.move_tab_to_other_split_action)
        view_menu.addSeparator()
        zoom_menu = view_menu.addMenu("Interface Zoom")
        zoom_menu.addAction(self.zoom_in_ui_action)
        zoom_menu.addAction(self.zoom_out_ui_action)
        zoom_menu.addAction(self.zoom_reset_ui_action)
        self._update_ui_zoom_actions()

        github_action = QAction("&GitHub Repository", self)
        github_action.triggered.connect(self._open_github_repo)
        help_menu.addAction(github_action)
        help_menu.addSeparator()

        about_action = QAction("&About Temcode", self)
        about_action.triggered.connect(lambda: self.statusBar().showMessage(f"Temcode Version {__version__}", 2500))
        help_menu.addAction(about_action)

        menu_bar = self.menuBar()
        menu_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        for menu in menu_bar.findChildren(QMenu):
            menu.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_status_bar(self) -> None:
        self.statusBar().showMessage("Ready")
        self.autosave_status_label = QLabel("Autosave: configuring")
        self.autosave_status_label.setObjectName("autosaveStatusLabel")
        self.language_status_label = QLabel("Plain Text")
        self.language_status_label.setObjectName("languageStatusLabel")
        self.large_file_status_label = QLabel("")
        self.large_file_status_label.setObjectName("largeFileStatusLabel")
        self.large_file_status_label.setStyleSheet("color: #f0c674; font-weight: 600;")
        self.lsp_status_label = QLabel("LSP: idle")
        self.lsp_status_label.setObjectName("lspStatusLabel")
        self.statusBar().addPermanentWidget(self.autosave_status_label)
        self.statusBar().addPermanentWidget(self.language_status_label)
        self.statusBar().addPermanentWidget(self.large_file_status_label)
        self.statusBar().addPermanentWidget(self.lsp_status_label)

    def _open_github_repo(self) -> None:
        opened = webbrowser.open(self._GITHUB_REPO_URL, new=2, autoraise=True)
        if not opened:
            self.statusBar().showMessage("Could not open GitHub repository.", 2500)

    def _build_central_editor_area(self) -> None:
        self.central_editor_widget = QWidget(self)
        self.central_editor_layout = QVBoxLayout(self.central_editor_widget)
        self.central_editor_layout.setContentsMargins(0, 0, 0, 0)
        self.central_editor_layout.setSpacing(0)

        self._build_find_panel()
        self._build_breadcrumbs_bar()

        self.editor_stack = QStackedWidget(self.central_editor_widget)
        self.welcome_widget = self._build_welcome_screen()
        self.editor_stack.addWidget(self.welcome_widget)

        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.editor_splitter.setChildrenCollapsible(False)

        self.primary_tabs = self._create_editor_tabs("primaryEditorTabs")
        self.secondary_tabs = self._create_editor_tabs("secondaryEditorTabs")

        self.editor_splitter.addWidget(self.primary_tabs)
        self.editor_splitter.addWidget(self.secondary_tabs)
        self.editor_splitter.setSizes([1200, 0])

        self.editor_stack.addWidget(self.editor_splitter)
        self.central_editor_layout.addWidget(self.editor_stack, 1)
        self.setCentralWidget(self.central_editor_widget)
        self._active_editor_tabs = self.primary_tabs
        self._set_split_enabled(False)
        self._update_editor_surface()

    def _build_find_panel(self) -> None:
        self.find_panel = QFrame(self)
        self.find_panel.setObjectName("findReplacePanel")
        self.find_panel.hide()

        panel_layout = QHBoxLayout(self.find_panel)
        panel_layout.setContentsMargins(10, 6, 10, 6)
        panel_layout.setSpacing(6)

        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find text")
        self.find_input.textChanged.connect(self._on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)

        self.find_prev_button = QPushButton("Prev")
        self.find_prev_button.clicked.connect(self.find_previous)

        self.find_next_button = QPushButton("Next")
        self.find_next_button.clicked.connect(self.find_next)

        self.replace_label = QLabel("Replace:")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.returnPressed.connect(self.replace_current)

        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_current)

        self.replace_all_button = QPushButton("Replace All")
        self.replace_all_button.clicked.connect(self.replace_all)

        self.close_find_button = QPushButton("Close")
        self.close_find_button.clicked.connect(self.close_find_panel)

        panel_layout.addWidget(self.find_label)
        panel_layout.addWidget(self.find_input, 1)
        panel_layout.addWidget(self.find_prev_button)
        panel_layout.addWidget(self.find_next_button)
        panel_layout.addWidget(self.replace_label)
        panel_layout.addWidget(self.replace_input, 1)
        panel_layout.addWidget(self.replace_button)
        panel_layout.addWidget(self.replace_all_button)
        panel_layout.addWidget(self.close_find_button)

        self.central_editor_layout.addWidget(self.find_panel, 0)
        self._set_replace_controls_visible(False)

    def _build_breadcrumbs_bar(self) -> None:
        self.breadcrumbs_bar = QFrame(self)
        self.breadcrumbs_bar.setObjectName("breadcrumbsBar")

        self.breadcrumbs_layout = QHBoxLayout(self.breadcrumbs_bar)
        self.breadcrumbs_layout.setContentsMargins(10, 4, 10, 4)
        self.breadcrumbs_layout.setSpacing(4)

        self.central_editor_layout.addWidget(self.breadcrumbs_bar, 0)
        self._render_breadcrumbs(["Workspace"])

    def _build_welcome_screen(self) -> QWidget:
        container = QWidget(self.central_editor_widget)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        panel = QFrame(container)
        panel.setObjectName("welcomeScreen")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 24, 28, 24)
        panel_layout.setSpacing(12)

        user_name = os.environ.get("USERNAME") or os.environ.get("USER") or os.getlogin()
        welcome_title = random.choice(self._WELCOME_TITLES).format(user=user_name)
        title_label = QLabel(welcome_title, panel)
        title_label.setObjectName("welcomeTitle")

        subtitle_label = QLabel(
            "Open or create a file/folder, or continue from a recent path.",
            panel,
        )
        subtitle_label.setObjectName("welcomeSubtitle")

        action_row = QWidget(panel)
        action_row_layout = QHBoxLayout(action_row)
        action_row_layout.setContentsMargins(0, 0, 0, 0)
        action_row_layout.setSpacing(8)

        new_file_button = QPushButton("New File...", action_row)
        new_file_button.setObjectName("welcomeActionButton")
        new_file_button.clicked.connect(self._create_file_from_welcome)

        new_folder_button = QPushButton("New Folder...", action_row)
        new_folder_button.setObjectName("welcomeActionButton")
        new_folder_button.clicked.connect(self._create_folder_from_welcome)

        open_file_button = QPushButton("Open File...", action_row)
        open_file_button.setObjectName("welcomeActionButton")
        open_file_button.clicked.connect(self.open_file_dialog)

        open_folder_button = QPushButton("Open Folder...", action_row)
        open_folder_button.setObjectName("welcomeActionButton")
        open_folder_button.clicked.connect(self.open_folder_dialog)

        open_recent_button = QPushButton("Open Selected Recent", action_row)
        open_recent_button.setObjectName("welcomeActionButton")
        open_recent_button.clicked.connect(self._open_selected_recent_path)

        action_row_layout.addWidget(new_file_button, 0)
        action_row_layout.addWidget(new_folder_button, 0)
        action_row_layout.addWidget(open_file_button, 0)
        action_row_layout.addWidget(open_folder_button, 0)
        action_row_layout.addWidget(open_recent_button, 0)
        action_row_layout.addStretch(1)

        recent_label = QLabel("Recent Files and Paths", panel)
        recent_label.setObjectName("welcomeRecentLabel")

        self.welcome_recent_list = QListWidget(panel)
        self.welcome_recent_list.setObjectName("welcomeRecentList")
        self.welcome_recent_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_recent_list.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.welcome_recent_list.itemActivated.connect(self._on_recent_item_activated)
        self.welcome_recent_list.itemDoubleClicked.connect(self._on_recent_item_activated)

        panel_layout.addWidget(title_label, 0)
        panel_layout.addWidget(subtitle_label, 0)
        panel_layout.addWidget(action_row, 0)
        panel_layout.addWidget(recent_label, 0)
        panel_layout.addWidget(self.welcome_recent_list, 1)
        container_layout.addWidget(panel, 1)

        return container

    def _has_open_editors(self) -> bool:
        return any(tabs.count() > 0 for tabs in self._all_tab_widgets())

    def _update_editor_surface(self) -> None:
        has_editors = self._has_open_editors()
        has_workspace = bool(self.workspace_root and os.path.isdir(self.workspace_root))
        show_editor_surface = has_editors or has_workspace
        self.editor_stack.setCurrentWidget(self.editor_splitter if show_editor_surface else self.welcome_widget)
        self.breadcrumbs_bar.setVisible(has_editors)
        if not has_editors and self.find_panel.isVisible():
            self.close_find_panel()
            self._refresh_breadcrumbs(None)

    def _refresh_welcome_recent_list(self) -> None:
        if not hasattr(self, "welcome_recent_list"):
            return

        self.welcome_recent_list.clear()
        if not self._recent_paths:
            empty_item = QListWidgetItem("No recent files or folders yet.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.welcome_recent_list.addItem(empty_item)
            return

        for path in self._recent_paths:
            absolute_path = os.path.abspath(path)
            if os.path.isdir(absolute_path):
                entry_kind = "Folder"
            elif os.path.isfile(absolute_path):
                entry_kind = "File"
            else:
                entry_kind = "Missing"

            item = QListWidgetItem(f"[{entry_kind}] {absolute_path}")
            item.setData(Qt.ItemDataRole.UserRole, absolute_path)
            if entry_kind == "Missing":
                item.setToolTip("Path not found. Activate to remove it from recents.")
            self.welcome_recent_list.addItem(item)

    def _open_selected_recent_path(self) -> None:
        selected_item = self.welcome_recent_list.currentItem()
        if selected_item is None:
            self.statusBar().showMessage("Choose a recent path first.", 1800)
            return
        self._open_recent_path(selected_item)

    def _on_recent_item_activated(self, item: object = None) -> None:
        resolved_item: QListWidgetItem | None = None
        if isinstance(item, QListWidgetItem):
            resolved_item = item
        elif isinstance(item, QModelIndex) and item.isValid():
            resolved_item = self.welcome_recent_list.itemFromIndex(item)
        elif hasattr(self, "welcome_recent_list"):
            resolved_item = self.welcome_recent_list.currentItem()

        self._open_recent_path(resolved_item)

    def _open_recent_path(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        path_value = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path_value, str) or not path_value:
            return

        absolute_path = os.path.abspath(path_value)
        if os.path.isdir(absolute_path):
            self.set_workspace_root(absolute_path)
            return

        if os.path.isfile(absolute_path):
            self.open_file(absolute_path)
            return

        QMessageBox.warning(
            self,
            "Recent Path Missing",
            f"This recent path no longer exists:\n{absolute_path}",
        )
        missing_key = self._normalize_path(absolute_path)
        self._recent_paths = [
            existing
            for existing in self._recent_paths
            if self._normalize_path(existing) != missing_key
        ]
        self._write_recent_paths()
        self._refresh_welcome_recent_list()

    def _refresh_breadcrumbs(self, widget: QWidget | None = None) -> None:
        target_widget = widget if widget is not None else self._current_tab_widget()
        self._render_breadcrumbs(self._breadcrumb_segments_for_widget(target_widget), target_widget)

    def _breadcrumb_segments_for_widget(self, widget: QWidget | None) -> list[str]:
        if widget is None:
            return ["Workspace"]

        file_path = self._widget_file_path(widget)
        if not file_path:
            return ["Workspace", self._widget_display_name(widget)]

        absolute_path = os.path.abspath(file_path)
        if self.workspace_root and self._is_same_or_child(absolute_path, self.workspace_root):
            relative_path = os.path.relpath(absolute_path, self.workspace_root)
            if relative_path in (".", ""):
                return ["Workspace", os.path.basename(absolute_path)]
            relative_parts = [
                part for part in relative_path.replace("/", os.sep).split(os.sep) if part and part != "."
            ]
            return ["Workspace", *relative_parts]

        drive, tail = os.path.splitdrive(absolute_path)
        tail_parts = [part for part in tail.strip("\\/").split(os.sep) if part]
        root_segment = f"{drive}\\" if drive else os.sep
        return ["Workspace", "(external)", root_segment, *tail_parts]

    def _render_breadcrumbs(self, segments: list[str], target_widget: QWidget | None = None) -> None:
        while self.breadcrumbs_layout.count():
            item = self.breadcrumbs_layout.takeAt(0)
            item_widget = item.widget()
            if item_widget is not None:
                item_widget.deleteLater()

        cleaned_segments = [segment for segment in segments if segment]
        if not cleaned_segments:
            cleaned_segments = ["Workspace"]

        for index, segment in enumerate(cleaned_segments):
            if index > 0:
                separator = QLabel(">")
                separator.setObjectName("breadcrumbSeparator")
                self.breadcrumbs_layout.addWidget(separator)

            label = QLabel(segment)
            label.setObjectName("breadcrumbSegment")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.breadcrumbs_layout.addWidget(label)

        self.breadcrumbs_layout.addStretch(1)
        self._add_python_run_button(target_widget)

    @staticmethod
    def _is_python_source_path(file_path: str | None) -> bool:
        if not file_path:
            return False
        return os.path.splitext(file_path)[1].lower() == ".py"

    def _python_file_path_for_widget(self, widget: QWidget | None) -> str | None:
        if not isinstance(widget, CodeEditor):
            return None
        file_path = self._editor_file_path(widget)
        if not self._is_python_source_path(file_path):
            return None
        return os.path.abspath(file_path)

    def _normalized_python_interpreter(self) -> str | None:
        raw_value = self._python_interpreter_path
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized or None

    def _add_python_run_button(self, widget: QWidget | None) -> None:
        python_file_path = self._python_file_path_for_widget(widget)
        if not python_file_path:
            return

        run_button = QPushButton(self.breadcrumbs_bar)
        run_button.setObjectName("pythonRunButton")
        run_button.setCursor(Qt.CursorShape.PointingHandCursor)

        interpreter = self._normalized_python_interpreter()
        if interpreter:
            run_button.setText("Run")
            run_button.setToolTip(f"Run {os.path.basename(python_file_path)}")
            run_button.clicked.connect(self._run_current_python_file)
        else:
            run_button.setText("Set Python Interpreter in Settings First")
            run_button.setToolTip("Set python.interpreter in Settings before running files.")
            run_button.clicked.connect(self._open_settings_for_python_interpreter)

        self.breadcrumbs_layout.addWidget(run_button)

    def _open_settings_for_python_interpreter(self) -> None:
        self.statusBar().showMessage("Set a Python interpreter in Settings first.", 3000)
        self.open_settings_dialog()

    def _run_current_python_file(self) -> None:
        current_widget = self._current_tab_widget()
        python_file_path = self._python_file_path_for_widget(current_widget)
        if not python_file_path:
            return

        interpreter = self._normalized_python_interpreter()
        if not interpreter:
            self._open_settings_for_python_interpreter()
            return

        if isinstance(current_widget, CodeEditor) and current_widget.document().isModified():
            answer = QMessageBox.question(
                self,
                "Run Python File",
                f"Save changes before running?\n{python_file_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Yes and not self._save_editor(current_widget, save_as=False):
                return

        if self.terminal_console is None:
            QMessageBox.warning(self, "Run Python File", "Terminal is not available.")
            return

        working_directory = os.path.dirname(python_file_path)
        if working_directory and os.path.isdir(working_directory):
            self.terminal_console.set_working_directory(working_directory)

        self.terminal_dock.show()
        self.terminal_dock.raise_()
        self.terminal_toggle_action.blockSignals(True)
        self.terminal_toggle_action.setChecked(True)
        self.terminal_toggle_action.blockSignals(False)

        command = subprocess.list2cmdline([interpreter, python_file_path])
        if not self.terminal_console.execute_command(command):
            self.statusBar().showMessage("Failed to run Python file in terminal.", 3000)
            self.log(f"[run] Failed to execute command: {command}")
            return

        self.statusBar().showMessage(f"Running {os.path.basename(python_file_path)}...", 2500)
        self.log(f"[run] {command}")

    def _create_editor_tabs(self, object_name: str) -> QTabWidget:
        tabs = QTabWidget(self)
        tabs.setObjectName(object_name)
        tabs.setDocumentMode(True)
        tabs.setMovable(True)
        tabs.setTabsClosable(False)
        tabs.currentChanged.connect(lambda i, t=tabs: self._on_current_tab_changed(t, i))
        tabs.tabBarClicked.connect(lambda _i, t=tabs: self._set_active_tab_widget(t))
        tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabs.tabBar().customContextMenuRequested.connect(
            lambda pos, t=tabs: self._show_tab_context_menu(t, pos)
        )
        return tabs

    def _add_editor_tab(self, tabs: QTabWidget, widget: QWidget, title: str) -> int:
        tab_index = tabs.addTab(widget, title)
        self._set_editor_tab_close_button(tabs, tab_index, widget)
        return tab_index

    def _set_editor_tab_close_button(self, tabs: QTabWidget, tab_index: int, widget: QWidget) -> None:
        close_button = QToolButton(tabs.tabBar())
        close_button.setObjectName("editorTabCloseButton")
        close_button.setText("X")
        close_button.setToolTip("Close")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setAutoRaise(True)
        close_button.setFixedSize(
            self._scaled_pixels(self._TAB_CLOSE_BUTTON_BASE_WIDTH),
            self._scaled_pixels(self._TAB_CLOSE_BUTTON_BASE_HEIGHT),
        )
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(
            lambda _checked=False, t=tabs, w=widget: self._close_editor_from_tab_button(t, w)
        )
        tabs.tabBar().setTabButton(tab_index, QTabBar.ButtonPosition.RightSide, close_button)

    def _close_editor_from_tab_button(self, tabs: QTabWidget, widget: QWidget) -> None:
        tab_index = tabs.indexOf(widget)
        if tab_index >= 0:
            self._request_close_tab(tabs, tab_index)
            return

        owner_tabs = self._find_tab_widget_for_editor(widget)
        if owner_tabs is None:
            return

        owner_index = owner_tabs.indexOf(widget)
        if owner_index >= 0:
            self._request_close_tab(owner_tabs, owner_index)

    def _scaled_pixels(self, base_px: int) -> int:
        scaled = int(round(base_px * (self._ui_zoom_percent / 100.0)))
        return max(1, scaled)

    def _refresh_tab_close_button_sizes(self) -> None:
        width = self._scaled_pixels(self._TAB_CLOSE_BUTTON_BASE_WIDTH)
        height = self._scaled_pixels(self._TAB_CLOSE_BUTTON_BASE_HEIGHT)
        for tabs in self._all_tab_widgets():
            tab_bar = tabs.tabBar()
            for tab_index in range(tabs.count()):
                button = tab_bar.tabButton(tab_index, QTabBar.ButtonPosition.RightSide)
                if isinstance(button, QToolButton):
                    button.setFixedSize(width, height)

    def _refresh_solution_nav_button_sizes(self) -> None:
        if not hasattr(self, "solution_nav_bar"):
            return

        nav_bar_width = self._scaled_pixels(46)
        nav_button_size = self._scaled_pixels(34)
        nav_icon_size = self._scaled_pixels(18)
        self.solution_nav_bar.setFixedWidth(nav_bar_width)

        button_names = (
            "solution_nav_explorer_button",
            "solution_nav_search_button",
            "solution_nav_git_button",
            "solution_nav_settings_button",
        )
        for button_name in button_names:
            button = getattr(self, button_name, None)
            if isinstance(button, QToolButton):
                button.setFixedSize(nav_button_size, nav_button_size)
                button.setIconSize(QSize(nav_icon_size, nav_icon_size))

    def _build_solution_explorer_dock(self) -> None:
        self.solution_explorer_dock = QDockWidget("Explorer", self)
        self.solution_explorer_dock.setObjectName("solutionExplorerDock")
        self.solution_explorer_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.file_tree = QTreeView()
        self.file_tree.setObjectName("workspaceTree")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.file_tree.doubleClicked.connect(self._on_tree_double_clicked)

        self.fs_model = QFileSystemModel(self.file_tree)
        self.fs_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.fs_model.setRootPath("")

        self.file_tree.setModel(self.fs_model)
        self.file_tree.hideColumn(1)
        self.file_tree.hideColumn(2)
        self.file_tree.hideColumn(3)

        self.solution_explorer_placeholder = QLabel(
            "No folder opened.\nUse File > Open Folder...",
            self.solution_explorer_dock,
        )
        self.solution_explorer_placeholder.setObjectName("solutionExplorerPlaceholder")
        self.solution_explorer_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.solution_explorer_placeholder.setWordWrap(True)

        self.solution_explorer_stack = QStackedWidget(self.solution_explorer_dock)
        self.solution_explorer_stack.addWidget(self.solution_explorer_placeholder)
        self.solution_explorer_stack.addWidget(self.file_tree)

        self.solution_search_page = self._build_solution_search_page(self.solution_explorer_dock)
        self.solution_git_page = self._build_solution_git_page(self.solution_explorer_dock)

        self.solution_side_panel_stack = QStackedWidget(self.solution_explorer_dock)
        self.solution_side_panel_stack.setObjectName("solutionSidePanelStack")
        self.solution_side_panel_stack.addWidget(self.solution_explorer_stack)
        self.solution_side_panel_stack.addWidget(self.solution_search_page)
        self.solution_side_panel_stack.addWidget(self.solution_git_page)

        dock_content = QWidget(self.solution_explorer_dock)
        dock_content_layout = QHBoxLayout(dock_content)
        dock_content_layout.setContentsMargins(0, 0, 0, 0)
        dock_content_layout.setSpacing(0)

        self.solution_nav_bar = QFrame(dock_content)
        self.solution_nav_bar.setObjectName("solutionNavBar")
        self.solution_nav_bar.setFrameShape(QFrame.Shape.NoFrame)
        self.solution_nav_bar.setFixedWidth(self._scaled_pixels(46))
        nav_layout = QVBoxLayout(self.solution_nav_bar)
        nav_layout.setContentsMargins(4, 8, 4, 8)
        nav_layout.setSpacing(4)

        nav_button_size = self._scaled_pixels(34)
        nav_icon_size = self._scaled_pixels(18)

        self.solution_nav_explorer_button = self._create_solution_nav_button(
            object_name="solutionNavExplorerButton",
            icon_type=QStyle.StandardPixmap.SP_DirOpenIcon,
            theme_icon_name="folder-open",
            tooltip_text="Workspace Explorer",
            button_size=nav_button_size,
            icon_size=nav_icon_size,
        )
        self.solution_nav_explorer_button.clicked.connect(lambda _checked=False: self._show_solution_panel("explorer"))
        nav_layout.addWidget(self.solution_nav_explorer_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.solution_nav_search_button = self._create_solution_nav_button(
            object_name="solutionNavSearchButton",
            icon_type=QStyle.StandardPixmap.SP_FileDialogContentsView,
            theme_icon_name="edit-find",
            tooltip_text="Search",
            button_size=nav_button_size,
            icon_size=nav_icon_size,
        )
        self.solution_nav_search_button.clicked.connect(lambda _checked=False: self._show_solution_panel("search"))
        nav_layout.addWidget(self.solution_nav_search_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.solution_nav_git_button = self._create_solution_nav_button(
            object_name="solutionNavGitButton",
            icon_type=QStyle.StandardPixmap.SP_BrowserReload,
            theme_icon_name="vcs-normal",
            tooltip_text="Git",
            button_size=nav_button_size,
            icon_size=nav_icon_size,
        )
        self.solution_nav_git_button.clicked.connect(lambda _checked=False: self._show_solution_panel("git"))
        nav_layout.addWidget(self.solution_nav_git_button, 0, Qt.AlignmentFlag.AlignHCenter)
        nav_layout.addStretch(1)

        self.solution_nav_settings_button = self._create_solution_nav_button(
            object_name="solutionNavSettingsButton",
            icon_type=QStyle.StandardPixmap.SP_FileDialogDetailedView,
            theme_icon_name="preferences-system",
            tooltip_text="Settings",
            button_size=nav_button_size,
            icon_size=nav_icon_size,
            checkable=False,
        )
        self.solution_nav_settings_button.clicked.connect(self.open_settings_dialog)
        nav_layout.addWidget(self.solution_nav_settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        dock_content_layout.addWidget(self.solution_nav_bar, 0)
        dock_content_layout.addWidget(self.solution_side_panel_stack, 1)

        self.solution_explorer_dock.setWidget(dock_content)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.solution_explorer_dock)
        self.solution_explorer_toggle_action.setCheckable(True)
        self.solution_explorer_toggle_action.setChecked(True)
        self.solution_explorer_toggle_action.toggled.connect(self.solution_explorer_dock.setVisible)
        self.solution_explorer_dock.visibilityChanged.connect(self._on_solution_explorer_dock_visibility_changed)
        self._show_solution_panel("explorer")
        self._update_solution_explorer_surface()

    def _create_solution_nav_button(
        self,
        object_name: str,
        icon_type: QStyle.StandardPixmap,
        theme_icon_name: str | None,
        tooltip_text: str,
        button_size: int,
        icon_size: int,
        *,
        checkable: bool = True,
    ) -> QToolButton:
        button = QToolButton(self.solution_nav_bar)
        button.setObjectName(object_name)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setAutoRaise(True)
        button.setCheckable(checkable)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(button_size, button_size)
        button.setIconSize(QSize(icon_size, icon_size))
        themed_icon = QIcon.fromTheme(theme_icon_name) if theme_icon_name else QIcon()
        button.setIcon(themed_icon if not themed_icon.isNull() else self.style().standardIcon(icon_type))
        button.setToolTip(tooltip_text)
        if checkable:
            button.setAutoExclusive(True)
        return button

    def _build_solution_search_page(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        page.setObjectName("solutionSearchPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.solution_search_input = QLineEdit(page)
        self.solution_search_input.setPlaceholderText("Search text in file/workspace")
        self.solution_search_input.returnPressed.connect(self._on_solution_search_requested)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(6)

        self.solution_search_scope_combo = QComboBox(page)
        self.solution_search_scope_combo.addItem("Current file", "current_file")
        self.solution_search_scope_combo.addItem("Workspace", "workspace")

        self.solution_search_case_checkbox = QCheckBox("Case sensitive", page)
        self.solution_search_run_button = QPushButton("Search", page)
        self.solution_search_run_button.clicked.connect(self._on_solution_search_requested)

        controls_row.addWidget(self.solution_search_scope_combo, 0)
        controls_row.addWidget(self.solution_search_case_checkbox, 0)
        controls_row.addStretch(1)
        controls_row.addWidget(self.solution_search_run_button, 0)

        self.solution_search_summary_label = QLabel("Enter text and press Search.", page)
        self.solution_search_summary_label.setWordWrap(True)

        self.solution_search_results = QListWidget(page)
        self.solution_search_results.setObjectName("solutionSearchResults")
        self.solution_search_results.itemActivated.connect(self._on_solution_search_result_activated)

        layout.addWidget(self.solution_search_input, 0)
        layout.addLayout(controls_row)
        layout.addWidget(self.solution_search_summary_label, 0)
        layout.addWidget(self.solution_search_results, 1)
        return page

    def _build_solution_git_page(self, parent: QWidget) -> QWidget:
        page = QWidget(parent)
        page.setObjectName("solutionGitPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.git_changes_header_label = QLabel("CHANGES", page)
        self.git_changes_header_label.setObjectName("gitSectionTitle")

        repo_row = QHBoxLayout()
        repo_row.setContentsMargins(0, 0, 0, 0)
        repo_row.setSpacing(6)

        self.git_repo_combo = QComboBox(page)
        self.git_repo_combo.setObjectName("gitRepoCombo")
        self.git_repo_combo.currentIndexChanged.connect(self._on_git_repository_changed)

        self.git_scan_button = QPushButton("Scan", page)
        self.git_scan_button.setObjectName("gitScanButton")
        self.git_scan_button.clicked.connect(lambda: self._refresh_git_repositories(preserve_selection=False))

        self.git_refresh_button = QPushButton("Refresh", page)
        self.git_refresh_button.setObjectName("gitRefreshButton")
        self.git_refresh_button.clicked.connect(self._refresh_git_status_and_remote_check)

        repo_row.addWidget(self.git_repo_combo, 1)
        repo_row.addWidget(self.git_scan_button, 0)
        repo_row.addWidget(self.git_refresh_button, 0)

        self.git_repo_summary_label = QLabel("No repository detected.", page)
        self.git_repo_summary_label.setWordWrap(True)

        branch_row = QHBoxLayout()
        branch_row.setContentsMargins(0, 0, 0, 0)
        branch_row.setSpacing(6)

        self.git_branch_combo = QComboBox(page)
        self.git_branch_combo.setObjectName("gitBranchCombo")

        self.git_checkout_button = QPushButton("Checkout", page)
        self.git_checkout_button.setObjectName("gitCheckoutButton")
        self.git_checkout_button.clicked.connect(self._git_checkout_selected_branch)

        self.git_new_branch_input = QLineEdit(page)
        self.git_new_branch_input.setObjectName("gitNewBranchInput")
        self.git_new_branch_input.setPlaceholderText("new-branch-name")
        self.git_new_branch_input.returnPressed.connect(self._git_create_and_checkout_branch)

        self.git_new_branch_button = QPushButton("Create + Checkout", page)
        self.git_new_branch_button.setObjectName("gitNewBranchButton")
        self.git_new_branch_button.clicked.connect(self._git_create_and_checkout_branch)

        branch_row.addWidget(self.git_branch_combo, 1)
        branch_row.addWidget(self.git_checkout_button, 0)
        branch_row.addWidget(self.git_new_branch_input, 1)
        branch_row.addWidget(self.git_new_branch_button, 0)

        remote_row = QHBoxLayout()
        remote_row.setContentsMargins(0, 0, 0, 0)
        remote_row.setSpacing(6)

        self.git_pull_button = QPushButton("Pull", page)
        self.git_pull_button.setObjectName("gitPullButton")
        self.git_pull_button.clicked.connect(self._git_pull)
        self.git_push_button = QPushButton("Push", page)
        self.git_push_button.setObjectName("gitPushButton")
        self.git_push_button.clicked.connect(self._git_push)
        self.git_sync_button = QPushButton("Sync", page)
        self.git_sync_button.setObjectName("gitSyncButton")
        self.git_sync_button.clicked.connect(self._git_sync)

        remote_row.addWidget(self.git_pull_button, 0)
        remote_row.addWidget(self.git_push_button, 0)
        remote_row.addWidget(self.git_sync_button, 0)
        remote_row.addStretch(1)

        commit_row = QHBoxLayout()
        commit_row.setContentsMargins(0, 0, 0, 0)
        commit_row.setSpacing(6)

        self.git_commit_input = QLineEdit(page)
        self.git_commit_input.setObjectName("gitCommitInput")
        self.git_commit_input.setPlaceholderText("Message (Enter to commit)")
        self.git_commit_input.returnPressed.connect(self._git_commit_changes)

        self.git_commit_button = QToolButton(page)
        self.git_commit_button.setObjectName("gitCommitSplitButton")
        self.git_commit_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.git_commit_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.git_commit_button.setText("Commit")
        self.git_commit_button.clicked.connect(self._git_commit_changes)

        self.git_commit_menu = QMenu(self.git_commit_button)
        self.git_commit_menu.setObjectName("gitCommitMenu")
        self.git_commit_action = QAction("Commit", self.git_commit_menu)
        self.git_commit_action.triggered.connect(self._git_commit_changes)
        self.git_commit_push_action = QAction("Commit & Push", self.git_commit_menu)
        self.git_commit_push_action.triggered.connect(self._git_commit_and_push)
        self.git_commit_menu.addAction(self.git_commit_action)
        self.git_commit_menu.addAction(self.git_commit_push_action)
        self.git_commit_button.setMenu(self.git_commit_menu)

        commit_row.addWidget(self.git_commit_input, 1)
        commit_row.addWidget(self.git_commit_button, 0)

        changes_actions_row = QHBoxLayout()
        changes_actions_row.setContentsMargins(0, 0, 0, 0)
        changes_actions_row.setSpacing(6)

        self.git_discard_selected_button = QPushButton("Discard Selected", page)
        self.git_discard_selected_button.clicked.connect(self._git_discard_selected)

        changes_actions_row.addWidget(self.git_discard_selected_button, 0)
        changes_actions_row.addStretch(1)

        destructive_row = QHBoxLayout()
        destructive_row.setContentsMargins(0, 0, 0, 0)
        destructive_row.setSpacing(6)

        self.git_reset_hard_button = QPushButton("Reset Hard", page)
        self.git_reset_hard_button.clicked.connect(self._git_reset_hard)
        self.git_clean_untracked_button = QPushButton("Clean Untracked", page)
        self.git_clean_untracked_button.clicked.connect(self._git_clean_untracked)
        self.git_open_file_button = QPushButton("Open Selected File", page)
        self.git_open_file_button.clicked.connect(self._git_open_selected_file)

        destructive_row.addWidget(self.git_reset_hard_button, 0)
        destructive_row.addWidget(self.git_clean_untracked_button, 0)
        destructive_row.addWidget(self.git_open_file_button, 0)
        destructive_row.addStretch(1)

        self.git_changes_list = QListWidget(page)
        self.git_changes_list.setObjectName("gitChangesList")
        self.git_changes_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.git_changes_list.itemSelectionChanged.connect(self._on_git_change_selection_changed)
        self.git_changes_list.itemActivated.connect(self._on_git_change_activated)

        self.git_diff_view = QPlainTextEdit(page)
        self.git_diff_view.setObjectName("gitDiffView")
        self.git_diff_view.setReadOnly(True)
        self.git_diff_view.setPlainText("Select a changed file to preview diff.")

        self.git_log_list = QListWidget(page)
        self.git_log_list.setObjectName("gitLogList")
        self.git_log_list.itemActivated.connect(self._on_git_log_activated)

        self.git_graph_header_label = QLabel("GRAPH", page)
        self.git_graph_header_label.setObjectName("gitSectionTitle")

        self.git_log_refresh_button = QPushButton("Refresh", page)
        self.git_log_refresh_button.setObjectName("gitRefreshLogButton")
        self.git_log_refresh_button.clicked.connect(self._refresh_git_log)

        list_splitter = QSplitter(Qt.Orientation.Vertical, page)
        list_splitter.addWidget(self.git_changes_list)
        list_splitter.addWidget(self.git_diff_view)
        list_splitter.setChildrenCollapsible(False)
        list_splitter.setSizes([280, 260])

        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(6)
        graph_header_row = QHBoxLayout()
        graph_header_row.setContentsMargins(0, 0, 0, 0)
        graph_header_row.setSpacing(6)
        graph_header_row.addWidget(self.git_graph_header_label, 0)
        graph_header_row.addStretch(1)
        graph_header_row.addWidget(self.git_log_refresh_button, 0)
        log_layout.addLayout(graph_header_row)
        log_layout.addWidget(self.git_log_list, 1)

        content_splitter = QSplitter(Qt.Orientation.Vertical, page)
        top_container = QWidget(page)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(list_splitter)
        content_splitter.addWidget(top_container)

        log_container = QWidget(page)
        log_container.setLayout(log_layout)
        content_splitter.addWidget(log_container)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setSizes([420, 180])

        layout.addWidget(self.git_changes_header_label, 0)
        layout.addLayout(repo_row)
        layout.addWidget(self.git_repo_summary_label, 0)
        layout.addLayout(branch_row)
        layout.addLayout(remote_row)
        layout.addLayout(commit_row)
        layout.addLayout(changes_actions_row)
        layout.addLayout(destructive_row)
        layout.addWidget(content_splitter, 1)

        return page

    def _show_solution_panel(self, panel_name: str) -> None:
        normalized = panel_name if panel_name in {"search", "git"} else "explorer"
        self._solution_nav_panel = normalized

        if normalized == "search":
            self.solution_side_panel_stack.setCurrentWidget(self.solution_search_page)
            self.solution_nav_search_button.setChecked(True)
            self.solution_search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif normalized == "git":
            self.solution_side_panel_stack.setCurrentWidget(self.solution_git_page)
            self.solution_nav_git_button.setChecked(True)
            workspace_key = self._normalize_path(self.workspace_root) if self.workspace_root else None
            has_cached_repos = bool(self._git_known_repositories)
            same_workspace_scan = workspace_key == self._git_repo_scan_workspace
            if has_cached_repos and same_workspace_scan:
                self._refresh_git_status_panel()
            else:
                self._refresh_git_repositories()
            QTimer.singleShot(0, lambda: self._check_git_remote_updates(force=True, prompt_for_pull=True))
        else:
            self.solution_side_panel_stack.setCurrentWidget(self.solution_explorer_stack)
            self.solution_nav_explorer_button.setChecked(True)

        self._refresh_solution_explorer_dock_title()

    def _refresh_solution_explorer_dock_title(self) -> None:
        if not hasattr(self, "solution_explorer_dock"):
            return
        if self._solution_nav_panel == "search":
            self.solution_explorer_dock.setWindowTitle("Search")
            return
        if self._solution_nav_panel == "git":
            self.solution_explorer_dock.setWindowTitle("Git")
            return

        if self.workspace_root and os.path.isdir(self.workspace_root):
            workspace_name = os.path.basename(self.workspace_root.rstrip("\\/")) or self.workspace_root
            self.solution_explorer_dock.setWindowTitle(f"Explorer - {workspace_name}")
            return
        self.solution_explorer_dock.setWindowTitle("Explorer")

    def _on_solution_search_requested(self) -> None:
        query = self.solution_search_input.text()
        if not query:
            self.solution_search_results.clear()
            self.solution_search_summary_label.setText("Enter text and press Search.")
            self.statusBar().showMessage("Search query is empty.", 1800)
            return

        scope_value = self.solution_search_scope_combo.currentData()
        scope = scope_value if isinstance(scope_value, str) else "current_file"
        case_sensitive = self.solution_search_case_checkbox.isChecked()

        if scope == "workspace":
            if not self.workspace_root or not os.path.isdir(self.workspace_root):
                self.solution_search_results.clear()
                self.solution_search_summary_label.setText("Open a workspace folder to search all files.")
                self.statusBar().showMessage("Open a workspace folder first.", 2200)
                return
            matches, truncated = self._search_workspace_for_text(query, case_sensitive=case_sensitive)
            scope_label = "workspace"
        else:
            if self._current_editor() is None:
                self.solution_search_results.clear()
                self.solution_search_summary_label.setText("Open a text file to search in the current file.")
                self.statusBar().showMessage("Open a text file first.", 2200)
                return
            matches, truncated = self._search_current_file_for_text(query, case_sensitive=case_sensitive)
            scope_label = "current file"

        self.solution_search_results.clear()
        for match in matches:
            self._add_solution_search_result_item(match)

        if matches:
            summary_text = f"Found {len(matches)} matches in {scope_label}."
            if truncated:
                summary_text = (
                    f"Found {len(matches)} matches in {scope_label} (stopped at {self._MAX_WORKSPACE_SEARCH_RESULTS})."
                )
        else:
            summary_text = f"No matches found in {scope_label}."

        self.solution_search_summary_label.setText(summary_text)
        self.statusBar().showMessage(summary_text, 2600)
        self.log(f"[search] {summary_text} query='{query}' case_sensitive={case_sensitive}")

    def _search_current_file_for_text(self, query: str, *, case_sensitive: bool) -> tuple[list[dict[str, object]], bool]:
        editor = self._current_editor()
        if editor is None:
            return [], False

        file_path = self._editor_file_path(editor)
        display_path = file_path or self._editor_display_name(editor)
        editor_token_value = editor.property("autosave_token")
        editor_token = editor_token_value if isinstance(editor_token_value, str) else None
        search_token = editor_token if file_path is None else None
        return self._collect_search_matches(
            text=editor.toPlainText(),
            query=query,
            display_path=display_path,
            file_path=file_path,
            case_sensitive=case_sensitive,
            max_results=self._MAX_WORKSPACE_SEARCH_RESULTS,
            editor_token=search_token,
        )

    def _search_workspace_for_text(self, query: str, *, case_sensitive: bool) -> tuple[list[dict[str, object]], bool]:
        if not self.workspace_root or not os.path.isdir(self.workspace_root):
            return [], False

        matches: list[dict[str, object]] = []
        truncated = False

        for root_path, directory_names, file_names in os.walk(self.workspace_root):
            directory_names[:] = [name for name in directory_names if name not in self._SEARCH_IGNORED_DIRECTORIES]

            for file_name in file_names:
                full_path = os.path.join(root_path, file_name)
                if self._is_image_file_path(full_path) or self._is_binary_file(full_path):
                    continue

                try:
                    file_text = self._read_text_file(full_path)
                except OSError:
                    continue

                remaining = self._MAX_WORKSPACE_SEARCH_RESULTS - len(matches)
                if remaining <= 0:
                    return matches, True

                try:
                    display_path = os.path.relpath(full_path, self.workspace_root)
                except ValueError:
                    display_path = full_path

                file_matches, file_truncated = self._collect_search_matches(
                    text=file_text,
                    query=query,
                    display_path=display_path,
                    file_path=full_path,
                    case_sensitive=case_sensitive,
                    max_results=remaining,
                )
                if file_matches:
                    matches.extend(file_matches)
                if file_truncated:
                    truncated = True
                    return matches, truncated

        return matches, truncated

    def _collect_search_matches(
        self,
        text: str,
        query: str,
        display_path: str,
        file_path: str | None,
        *,
        case_sensitive: bool,
        max_results: int,
        editor_token: str | None = None,
    ) -> tuple[list[dict[str, object]], bool]:
        if max_results <= 0 or not query:
            return [], False

        matches: list[dict[str, object]] = []
        needle = query if case_sensitive else query.lower()
        step_size = max(1, len(query))

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            searchable_line = raw_line if case_sensitive else raw_line.lower()
            start_index = 0

            while True:
                match_index = searchable_line.find(needle, start_index)
                if match_index < 0:
                    break

                snippet = raw_line.strip()
                if len(snippet) > self._SEARCH_SNIPPET_MAX_LENGTH:
                    snippet = snippet[: self._SEARCH_SNIPPET_MAX_LENGTH - 1] + "..."

                matches.append(
                    {
                        "display_path": display_path,
                        "file_path": file_path,
                        "line": line_number,
                        "column": match_index + 1,
                        "snippet": snippet,
                        "editor_token": editor_token,
                    }
                )

                if len(matches) >= max_results:
                    return matches, True

                start_index = match_index + step_size

        return matches, False

    def _add_solution_search_result_item(self, payload: dict[str, object]) -> None:
        display_path = payload.get("display_path") if isinstance(payload.get("display_path"), str) else "<unknown>"
        line_value = payload.get("line")
        column_value = payload.get("column")
        line_number = int(line_value) if isinstance(line_value, int) else 1
        column_number = int(column_value) if isinstance(column_value, int) else 1
        snippet = payload.get("snippet") if isinstance(payload.get("snippet"), str) else ""
        text = f"{display_path}:{line_number}:{column_number}  {snippet}"

        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, payload)
        item.setToolTip(text)
        self.solution_search_results.addItem(item)

    def _on_solution_search_result_activated(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return

        line_value = payload.get("line")
        column_value = payload.get("column")
        try:
            line = max(0, int(line_value) - 1)
            column = max(0, int(column_value) - 1)
        except (TypeError, ValueError):
            line = 0
            column = 0

        file_path = payload.get("file_path")
        if isinstance(file_path, str) and file_path:
            self._jump_to_file_location(file_path, line, column)
            return

        editor = self._resolve_editor_from_search_payload(payload)
        if editor is None:
            self.statusBar().showMessage("Search source is no longer open.", 2200)
            return

        self._jump_to_editor_location(editor, line, column)
        self.statusBar().showMessage(f"Search: line {line + 1}, column {column + 1}", 2200)

    def _resolve_editor_from_search_payload(self, payload: dict[str, object]) -> CodeEditor | None:
        token_value = payload.get("editor_token")
        if isinstance(token_value, str) and token_value:
            for editor in self._open_editors():
                editor_token_value = editor.property("autosave_token")
                if isinstance(editor_token_value, str) and editor_token_value == token_value:
                    return editor
            return None
        return self._current_editor()

    @staticmethod
    def _is_binary_file(file_path: str) -> bool:
        try:
            with open(file_path, "rb") as handle:
                sample = handle.read(4096)
        except OSError:
            return False
        return b"\x00" in sample

    @staticmethod
    def _decode_git_output(raw: bytes) -> str:
        if not raw:
            return ""
        for encoding in ("utf-8", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _run_git_command_raw(
        self,
        repository_path: str,
        args: list[str],
        *,
        timeout_seconds: int | None = None,
    ) -> tuple[bool, bytes, str, int]:
        timeout = timeout_seconds if isinstance(timeout_seconds, int) and timeout_seconds > 0 else self._GIT_COMMAND_TIMEOUT_SECONDS
        command = ["git", "-C", repository_path, *args]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError:
            return False, b"", "System git executable was not found.", -1
        except subprocess.TimeoutExpired:
            return False, b"", f"Command timed out after {timeout} seconds.", -1
        except OSError as exc:
            return False, b"", str(exc), -1

        stderr_text = self._decode_git_output(completed.stderr).strip()
        return completed.returncode == 0, bytes(completed.stdout), stderr_text, int(completed.returncode)

    def _run_git_command(
        self,
        repository_path: str,
        args: list[str],
        *,
        timeout_seconds: int | None = None,
    ) -> tuple[bool, str, str, int]:
        ok, stdout_raw, stderr_text, exit_code = self._run_git_command_raw(
            repository_path,
            args,
            timeout_seconds=timeout_seconds,
        )
        stdout_text = self._decode_git_output(stdout_raw).rstrip()
        return ok, stdout_text, stderr_text, exit_code

    def _git_repository_display_text(self, repository_path: str) -> str:
        absolute_repo = os.path.abspath(repository_path)
        if self.workspace_root and self._is_same_or_child(absolute_repo, self.workspace_root):
            try:
                relative = os.path.relpath(absolute_repo, self.workspace_root)
            except ValueError:
                relative = absolute_repo
            if relative in {".", ""}:
                return f"{os.path.basename(absolute_repo)} (workspace)"
            return relative
        return absolute_repo

    def _discover_git_repositories(self) -> list[str]:
        discovered: dict[str, str] = {}
        started_at = time.monotonic()
        scanned_directories = 0
        truncated_scan = False

        def add_from_probe(probe_path: str) -> None:
            normalized_probe = os.path.abspath(probe_path)
            if not os.path.isdir(normalized_probe):
                return
            ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
                normalized_probe,
                ["rev-parse", "--show-toplevel"],
                timeout_seconds=20,
            )
            if not ok or not stdout_text:
                return
            repo_root = os.path.abspath(stdout_text.splitlines()[0].strip())
            repo_key = self._normalize_path(repo_root)
            discovered[repo_key] = repo_root

        if self.workspace_root and os.path.isdir(self.workspace_root):
            workspace = os.path.abspath(self.workspace_root)
            add_from_probe(workspace)

            for root_path, directory_names, file_names in os.walk(workspace):
                scanned_directories += 1
                if scanned_directories >= self._GIT_DISCOVERY_MAX_DIRECTORIES:
                    truncated_scan = True
                    break
                if (time.monotonic() - started_at) >= self._GIT_DISCOVERY_MAX_SECONDS:
                    truncated_scan = True
                    break

                has_git = ".git" in directory_names or ".git" in file_names
                if has_git:
                    add_from_probe(root_path)

                directory_names[:] = [
                    name
                    for name in directory_names
                    if name not in self._SEARCH_IGNORED_DIRECTORIES
                ]
        else:
            current_widget = self._current_tab_widget()
            current_file_path = self._widget_file_path(current_widget) if current_widget is not None else None
            if current_file_path:
                add_from_probe(os.path.dirname(os.path.abspath(current_file_path)))
            add_from_probe(os.getcwd())

        if truncated_scan:
            self.log(
                "[git] Repository discovery hit scan limit. Use Git > Scan to refresh if needed."
            )

        workspace_absolute = os.path.abspath(self.workspace_root) if self.workspace_root else None
        ordered = sorted(
            discovered.values(),
            key=lambda path: (
                0 if workspace_absolute and self._is_same_or_child(path, workspace_absolute) else 1,
                len(path),
                self._normalize_path(path),
            ),
        )
        return ordered

    def _refresh_git_repositories(self, preserve_selection: bool = True) -> None:
        if not hasattr(self, "git_repo_combo"):
            return

        previous_repo = self._git_active_repository if preserve_selection else None
        repos = self._discover_git_repositories()
        self._git_known_repositories = repos
        self._git_repo_scan_workspace = self._normalize_path(self.workspace_root) if self.workspace_root else None

        self.git_repo_combo.blockSignals(True)
        self.git_repo_combo.clear()
        for repo_path in repos:
            self.git_repo_combo.addItem(self._git_repository_display_text(repo_path), repo_path)

        if not repos:
            self._git_active_repository = None
            self.git_repo_combo.blockSignals(False)
            self.git_repo_summary_label.setText("No Git repository detected in the current workspace.")
            self.git_changes_list.clear()
            self.git_branch_combo.clear()
            self.git_log_list.clear()
            self.git_diff_view.setPlainText("Diff preview will appear here.")
            self._set_git_controls_enabled(False)
            return

        selected_index = 0
        if previous_repo:
            previous_key = self._normalize_path(previous_repo)
            for index, repo_path in enumerate(repos):
                if self._normalize_path(repo_path) == previous_key:
                    selected_index = index
                    break

        self.git_repo_combo.setCurrentIndex(selected_index)
        selected_repo = self.git_repo_combo.currentData()
        self._git_active_repository = selected_repo if isinstance(selected_repo, str) else repos[selected_index]
        self.git_repo_combo.blockSignals(False)
        self._set_git_controls_enabled(True)
        self._refresh_git_status_panel()

    def _set_git_controls_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "git_repo_combo"):
            return

        controls = (
            self.git_refresh_button,
            self.git_branch_combo,
            self.git_checkout_button,
            self.git_new_branch_input,
            self.git_new_branch_button,
            self.git_pull_button,
            self.git_push_button,
            self.git_sync_button,
            self.git_commit_input,
            self.git_commit_button,
            self.git_discard_selected_button,
            self.git_reset_hard_button,
            self.git_clean_untracked_button,
            self.git_open_file_button,
            self.git_changes_list,
            self.git_diff_view,
            self.git_log_refresh_button,
            self.git_log_list,
        )
        for control in controls:
            control.setEnabled(enabled)

    def _active_git_repository(self) -> str | None:
        if self._git_active_repository and os.path.isdir(self._git_active_repository):
            return os.path.abspath(self._git_active_repository)
        return None

    def _on_git_repository_changed(self, _index: int) -> None:
        selected_repo = self.git_repo_combo.currentData()
        if isinstance(selected_repo, str) and selected_repo:
            self._git_active_repository = os.path.abspath(selected_repo)
            self._set_git_controls_enabled(True)
            self._refresh_git_status_panel()
            if self._solution_nav_panel == "git":
                QTimer.singleShot(0, lambda: self._check_git_remote_updates(force=True, prompt_for_pull=True))
            return

        self._git_active_repository = None
        self._set_git_controls_enabled(False)
        self.git_repo_summary_label.setText("No repository selected.")
        self.git_changes_list.clear()
        self.git_branch_combo.clear()
        self.git_log_list.clear()
        self.git_diff_view.setPlainText("Diff preview will appear here.")

    def _refresh_git_status_and_remote_check(self) -> None:
        self._refresh_git_status_panel()
        self._check_git_remote_updates(force=True, prompt_for_pull=True)

    def _refresh_git_status_panel(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self.git_repo_summary_label.setText("No repository selected.")
            return

        self._refresh_git_status()
        self._refresh_git_branches()
        self._refresh_git_log()

    def _parse_git_status_porcelain(self, payload: bytes) -> tuple[str, list[dict[str, object]]]:
        branch_summary = ""
        entries: list[dict[str, object]] = []
        tokens = payload.split(b"\0")
        index = 0

        while index < len(tokens):
            token = tokens[index]
            index += 1
            if not token:
                continue

            decoded = self._decode_git_output(token)
            if decoded.startswith("## "):
                branch_summary = decoded[3:].strip()
                continue
            if len(decoded) < 3:
                continue

            status = decoded[:2]
            raw_path = decoded[3:]
            old_path: str | None = None
            new_path: str | None = None
            display_path = raw_path
            operation_path = raw_path

            if status != "??" and ("R" in status or "C" in status):
                if index < len(tokens):
                    rename_target_token = tokens[index]
                    index += 1
                    if rename_target_token:
                        new_path = self._decode_git_output(rename_target_token)
                        old_path = raw_path
                        operation_path = new_path
                        display_path = f"{old_path} -> {new_path}"

            staged = status[0] not in {" ", "?"}
            unstaged = status[1] not in {" "}
            untracked = status == "??"

            entries.append(
                {
                    "status": status,
                    "path": operation_path,
                    "display_path": display_path,
                    "old_path": old_path,
                    "new_path": new_path,
                    "staged": staged,
                    "unstaged": unstaged,
                    "untracked": untracked,
                }
            )
            if len(entries) >= self._GIT_STATUS_MAX_ENTRIES:
                break

        return branch_summary, entries

    def _git_status_badge(self, entry: dict[str, object]) -> str:
        status_value = entry.get("status")
        status = status_value if isinstance(status_value, str) else "  "
        if status == "??":
            return "UNTRACKED"
        if status == "!!":
            return "IGNORED"

        staged = bool(entry.get("staged"))
        unstaged = bool(entry.get("unstaged"))
        if staged and unstaged:
            return "INDEX+MOD"
        if staged:
            return "INDEX"
        if unstaged:
            return "MODIFIED"
        return status.strip() or "CLEAN"

    def _refresh_git_status(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self._git_status_entries = []
            self.git_changes_list.clear()
            self.git_diff_view.setPlainText("Diff preview will appear here.")
            return

        ok, stdout_raw, stderr_text, _exit_code = self._run_git_command_raw(
            repository_path,
            ["status", "--porcelain=v1", "--branch", "-z"],
            timeout_seconds=30,
        )
        if not ok:
            self._git_status_entries = []
            self.git_changes_list.clear()
            error_detail = stderr_text or "Could not read git status."
            self.git_repo_summary_label.setText(error_detail)
            self.git_diff_view.setPlainText(error_detail)
            return

        previous_selected_paths = {
            payload.get("path")
            for payload in self._selected_git_entries()
            if isinstance(payload.get("path"), str)
        }

        self._git_branch_summary, self._git_status_entries = self._parse_git_status_porcelain(stdout_raw)

        self.git_changes_list.blockSignals(True)
        self.git_changes_list.clear()

        def add_section(section_title: str, entries: list[dict[str, object]]) -> None:
            header_item = QListWidgetItem(f"{section_title} ({len(entries)})")
            header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            header_item.setData(Qt.ItemDataRole.UserRole, None)
            header_item.setData(Qt.ItemDataRole.UserRole + 1, "header")
            header_font = header_item.font()
            header_font.setBold(True)
            header_item.setFont(header_font)
            self.git_changes_list.addItem(header_item)

            for entry in entries:
                display_path = entry.get("display_path")
                path_label = display_path if isinstance(display_path, str) else "<unknown>"
                badge = self._git_status_badge(entry)
                item_text = f"  {path_label}  [{badge}]"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                item.setData(Qt.ItemDataRole.UserRole + 1, "change")
                item.setToolTip(item_text)
                self.git_changes_list.addItem(item)

        add_section("Changes", self._git_status_entries)

        if previous_selected_paths:
            remaining_selected_paths = set(previous_selected_paths)
            for index in range(self.git_changes_list.count()):
                item = self.git_changes_list.item(index)
                payload = item.data(Qt.ItemDataRole.UserRole)
                if not isinstance(payload, dict):
                    continue
                path_value = payload.get("path")
                if path_value in remaining_selected_paths:
                    item.setSelected(True)
                    remaining_selected_paths.discard(path_value)

        self.git_changes_list.blockSignals(False)

        self._update_git_repo_summary_label()
        if self.git_changes_list.selectedItems():
            self._on_git_change_selection_changed()
        else:
            self.git_diff_view.setPlainText("Select a changed file to preview diff.")

    def _update_git_repo_summary_label(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self.git_repo_summary_label.setText("No repository selected.")
            return

        tracked_count = sum(1 for entry in self._git_status_entries if not entry.get("untracked"))
        untracked_count = sum(1 for entry in self._git_status_entries if entry.get("untracked"))

        summary_parts: list[str] = []
        if self._git_branch_summary:
            summary_parts.append(self._git_branch_summary)
        summary_parts.append(
            f"{len(self._git_status_entries)} local change(s) | tracked={tracked_count}, untracked={untracked_count}"
        )

        repo_key = self._normalize_path(repository_path)
        remote_delta = self._git_remote_delta_by_repo.get(repo_key)
        if remote_delta is not None:
            ahead_count, behind_count = remote_delta
            if ahead_count > 0 or behind_count > 0:
                summary_parts.append(f"remote: {behind_count} behind, {ahead_count} ahead")
            else:
                summary_parts.append("remote: up to date")

        self.git_repo_summary_label.setText(" | ".join(summary_parts))

    def _selected_git_entries(self) -> list[dict[str, object]]:
        if not hasattr(self, "git_changes_list"):
            return []
        entries: list[dict[str, object]] = []
        seen: set[tuple[str, str, bool, bool, bool]] = set()
        for item in self.git_changes_list.selectedItems():
            payload = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict):
                path_value = payload.get("path")
                status_value = payload.get("status")
                if not isinstance(path_value, str) or not path_value:
                    continue
                status_text = status_value if isinstance(status_value, str) else ""
                dedupe_key = (
                    path_value,
                    status_text,
                    bool(payload.get("staged")),
                    bool(payload.get("unstaged")),
                    bool(payload.get("untracked")),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries.append(payload)
        return entries

    def _on_git_change_selection_changed(self) -> None:
        entries = self._selected_git_entries()
        if not entries:
            self.git_diff_view.setPlainText("Diff preview will appear here.")
            return
        self._show_git_diff_for_entry(entries[0])

    def _on_git_change_activated(self, _item: QListWidgetItem) -> None:
        self._git_open_selected_file()

    def _show_git_diff_for_entry(self, entry: dict[str, object]) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self.git_diff_view.setPlainText("No active repository.")
            return

        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            self.git_diff_view.setPlainText("No path for selected entry.")
            return

        if entry.get("untracked"):
            absolute_path = os.path.join(repository_path, path_value)
            if os.path.isdir(absolute_path):
                self.git_diff_view.setPlainText(f"Untracked directory:\n{path_value}")
                return

            if os.path.isfile(absolute_path):
                try:
                    content = self._read_text_file(absolute_path)
                except OSError as exc:
                    self.git_diff_view.setPlainText(f"Could not read untracked file:\n{exc}")
                    return
                preview_limit = 20_000
                preview = content[:preview_limit]
                if len(content) > preview_limit:
                    preview += "\n\n... [truncated]"
                self.git_diff_view.setPlainText(f"Untracked file: {path_value}\n\n{preview}")
                return

            self.git_diff_view.setPlainText(f"Untracked path:\n{path_value}")
            return

        ok, stdout_text, stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["--no-pager", "diff", "HEAD", "--", path_value],
            timeout_seconds=30,
        )
        if ok:
            self.git_diff_view.setPlainText(stdout_text or "No diff output for selected entry.")
            return
        self.git_diff_view.setPlainText(stderr_text or "Could not load diff for selected entry.")

    def _git_open_selected_file(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        entries = self._selected_git_entries()
        if not entries:
            self.statusBar().showMessage("Select a file from Git changes first.", 1800)
            return

        entry = entries[0]
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            return

        absolute_path = os.path.join(repository_path, path_value)
        if os.path.isfile(absolute_path):
            self.open_file(absolute_path)
            return
        self.statusBar().showMessage(f"Path is not a file: {path_value}", 2200)

    def _execute_git_command(
        self,
        repository_path: str,
        args: list[str],
        *,
        action_label: str,
        timeout_seconds: int | None = None,
        show_error_dialog: bool = True,
    ) -> bool:
        ok, stdout_text, stderr_text, exit_code = self._run_git_command(
            repository_path,
            args,
            timeout_seconds=timeout_seconds,
        )

        repo_label = os.path.basename(repository_path.rstrip("\\/")) or repository_path
        command_text = "git " + " ".join(args)
        self.log(f"[git:{repo_label}] {command_text}")
        if stdout_text:
            for line in stdout_text.splitlines():
                self.log(f"[git:{repo_label}] {line}")
        if stderr_text:
            for line in stderr_text.splitlines():
                self.log(f"[git:{repo_label}] {line}")

        if ok:
            self.statusBar().showMessage(f"Git {action_label} completed.", 2500)
            return True

        error_text = stderr_text or stdout_text or f"Command failed with exit code {exit_code}."
        self.statusBar().showMessage(f"Git {action_label} failed.", 3500)
        if show_error_dialog:
            QMessageBox.warning(
                self,
                f"Git {action_label.title()} Failed",
                error_text,
            )
        return False

    def _git_restore_path(self, repository_path: str, path_value: str) -> bool:
        if self._execute_git_command(
            repository_path,
            ["restore", "--source=HEAD", "--staged", "--worktree", "--", path_value],
            action_label="restore",
            show_error_dialog=False,
        ):
            return True
        return self._execute_git_command(
            repository_path,
            ["checkout", "HEAD", "--", path_value],
            action_label="restore",
            show_error_dialog=False,
        )

    def _git_discard_selected(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        entries = self._selected_git_entries()
        if not entries:
            self.statusBar().showMessage("Select one or more files to discard changes.", 2200)
            return

        answer = QMessageBox.warning(
            self,
            "Discard Selected Changes",
            "This will permanently discard selected Git changes.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        success = True
        for entry in entries:
            path_value = entry.get("path")
            if not isinstance(path_value, str) or not path_value:
                continue
            if entry.get("untracked"):
                if not self._execute_git_command(
                    repository_path,
                    ["clean", "-fd", "--", path_value],
                    action_label="discard untracked",
                    show_error_dialog=False,
                ):
                    success = False
                continue

            if not self._git_restore_path(repository_path, path_value):
                success = False

        if not success:
            QMessageBox.warning(self, "Discard Changes", "Some selected changes could not be discarded. See Output.")
        self._refresh_git_status_panel()

    def _git_reset_hard(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        answer = QMessageBox.warning(
            self,
            "Git Reset Hard",
            "This will run `git reset --hard HEAD` and permanently discard local tracked changes.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._execute_git_command(
            repository_path,
            ["reset", "--hard", "HEAD"],
            action_label="reset hard",
        )
        self._refresh_git_status_panel()

    def _git_clean_untracked(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        answer = QMessageBox.warning(
            self,
            "Clean Untracked",
            "This will run `git clean -fd` and permanently delete untracked files and directories.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._execute_git_command(repository_path, ["clean", "-fd"], action_label="clean untracked")
        self._refresh_git_status_panel()

    def _git_commit_changes(self) -> bool:
        repository_path = self._active_git_repository()
        if not repository_path:
            return False

        message = self.git_commit_input.text().strip()
        if not message:
            self.statusBar().showMessage("Commit message is empty.", 2200)
            return False

        has_changes, _change_count = self._git_local_change_summary(repository_path)
        if not has_changes:
            self.statusBar().showMessage("No local changes to commit.", 2200)
            return False

        if not self._execute_git_command(
            repository_path,
            ["add", "-A"],
            action_label="add all",
        ):
            self._refresh_git_status_panel()
            return False

        committed = self._execute_git_command(
            repository_path,
            ["commit", "-m", message],
            action_label="commit",
        )
        if committed:
            self.git_commit_input.clear()
        self._refresh_git_status_panel()
        return committed

    def _git_commit_and_push(self) -> None:
        if not self._git_commit_changes():
            return
        self._git_push()

    def _refresh_git_branches(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self.git_branch_combo.clear()
            return

        ok_current, current_branch_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["branch", "--show-current"],
            timeout_seconds=20,
        )
        current_branch = current_branch_text.strip() if ok_current else ""

        ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["for-each-ref", "--format=%(refname:short)", "refs/heads"],
            timeout_seconds=20,
        )
        branches = [line.strip() for line in stdout_text.splitlines() if line.strip()] if ok else []
        if current_branch and current_branch not in branches:
            branches.insert(0, current_branch)

        self.git_branch_combo.blockSignals(True)
        self.git_branch_combo.clear()
        for branch_name in branches:
            self.git_branch_combo.addItem(branch_name, branch_name)
        if current_branch:
            index = self.git_branch_combo.findData(current_branch)
            if index >= 0:
                self.git_branch_combo.setCurrentIndex(index)
        self.git_branch_combo.blockSignals(False)

    def _git_current_branch(self, repository_path: str) -> str | None:
        ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["branch", "--show-current"],
            timeout_seconds=20,
        )
        if not ok:
            return None
        branch_name = stdout_text.strip()
        return branch_name or None

    def _git_upstream_branch(self, repository_path: str) -> str | None:
        ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            timeout_seconds=20,
        )
        if not ok:
            return None
        upstream_branch = stdout_text.strip()
        return upstream_branch or None

    def _git_default_remote_for_branch(self, repository_path: str, branch_name: str | None) -> str | None:
        if branch_name:
            ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
                repository_path,
                ["config", f"branch.{branch_name}.remote"],
                timeout_seconds=20,
            )
            configured_remote = stdout_text.strip() if ok else ""
            if configured_remote:
                return configured_remote

        ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["remote"],
            timeout_seconds=20,
        )
        if not ok:
            return None

        remotes = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        if not remotes:
            return None
        if "origin" in remotes:
            return "origin"
        return remotes[0]

    def _git_local_change_summary(self, repository_path: str) -> tuple[bool, int]:
        ok, stdout_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["status", "--porcelain=v1"],
            timeout_seconds=20,
        )
        if not ok:
            return False, 0

        entries = [line for line in stdout_text.splitlines() if line.strip()]
        return bool(entries), len(entries)

    def _check_git_remote_updates(self, *, force: bool = False, prompt_for_pull: bool = True) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        repo_key = self._normalize_path(repository_path)
        now = time.monotonic()
        if not force:
            last_checked = self._git_last_remote_check_by_repo.get(repo_key, 0.0)
            if (now - last_checked) < self._GIT_REMOTE_CHECK_MIN_INTERVAL_SECONDS:
                return
        self._git_last_remote_check_by_repo[repo_key] = now

        upstream_branch = self._git_upstream_branch(repository_path)
        if not upstream_branch:
            self._git_remote_delta_by_repo.pop(repo_key, None)
            self._update_git_repo_summary_label()
            return

        remote_name = upstream_branch.split("/", 1)[0] if "/" in upstream_branch else ""
        if not remote_name:
            current_branch = self._git_current_branch(repository_path)
            resolved_remote = self._git_default_remote_for_branch(repository_path, current_branch)
            if not resolved_remote:
                return
            remote_name = resolved_remote

        fetch_args = ["fetch", "--prune", "--quiet", remote_name]
        ok_fetch, _stdout_text, stderr_text, _exit_code = self._run_git_command(
            repository_path,
            fetch_args,
            timeout_seconds=self._GIT_REMOTE_CHECK_TIMEOUT_SECONDS,
        )
        repo_label = os.path.basename(repository_path.rstrip("\\/")) or repository_path
        self.log(f"[git:{repo_label}] git {' '.join(fetch_args)}")
        if stderr_text:
            for line in stderr_text.splitlines():
                self.log(f"[git:{repo_label}] {line}")
        if not ok_fetch:
            self.statusBar().showMessage("Git remote check failed. See Output for details.", 2800)
            return

        ok_counts, counts_text, counts_error_text, _exit_code = self._run_git_command(
            repository_path,
            ["rev-list", "--left-right", "--count", "HEAD...@{u}"],
            timeout_seconds=20,
        )
        if not ok_counts:
            if counts_error_text:
                for line in counts_error_text.splitlines():
                    self.log(f"[git:{repo_label}] {line}")
            return

        parts = counts_text.split()
        if len(parts) < 2:
            return

        try:
            ahead_count = int(parts[0])
            behind_count = int(parts[1])
        except ValueError:
            return

        self._git_remote_delta_by_repo[repo_key] = (ahead_count, behind_count)
        self._update_git_repo_summary_label()

        if behind_count <= 0:
            self._git_remote_prompted_head_by_repo.pop(repo_key, None)
            return
        if not prompt_for_pull:
            return

        ok_upstream_head, upstream_head_text, _stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["rev-parse", "@{u}"],
            timeout_seconds=20,
        )
        upstream_head = upstream_head_text.strip() if ok_upstream_head and upstream_head_text.strip() else upstream_branch
        if self._git_remote_prompted_head_by_repo.get(repo_key) == upstream_head:
            return

        answer = QMessageBox.question(
            self,
            "Remote Updates Available",
            f"Remote has {behind_count} new commit(s) on {upstream_branch}.\n\nPull now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._git_pull()
            self._check_git_remote_updates(force=True, prompt_for_pull=False)
            return
        self._git_remote_prompted_head_by_repo[repo_key] = upstream_head

    def _refresh_after_git_worktree_change(self) -> None:
        self._refresh_workspace_tree_after_external_change()

        open_paths: list[str] = []
        for tabs in self._all_tab_widgets():
            for index in range(tabs.count()):
                widget = self._tab_widget_at(tabs, index)
                if widget is None:
                    continue
                file_path = self._widget_file_path(widget)
                if not file_path:
                    continue
                open_paths.append(file_path)

        for file_path in open_paths:
            self._handle_external_file_change(file_path, source="poll")

        # Re-sync watcher/signature state after applying in-editor reloads.
        self._sync_file_watcher_paths()

    def _git_checkout_selected_branch(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return
        branch_value = self.git_branch_combo.currentData()
        if not isinstance(branch_value, str) or not branch_value.strip():
            self.statusBar().showMessage("Select a branch to checkout.", 2200)
            return
        self._execute_git_command(
            repository_path,
            ["checkout", branch_value.strip()],
            action_label="checkout",
        )
        self._refresh_after_git_worktree_change()
        self._refresh_git_status_panel()

    def _git_create_and_checkout_branch(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        branch_name = self.git_new_branch_input.text().strip()
        if not branch_name:
            self.statusBar().showMessage("Enter a new branch name first.", 2200)
            return

        if self._execute_git_command(
            repository_path,
            ["checkout", "-b", branch_name],
            action_label="create branch",
        ):
            self.git_new_branch_input.clear()
            self._refresh_after_git_worktree_change()
        self._refresh_git_status_panel()

    def _git_pull(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        branch_name = self._git_current_branch(repository_path)
        upstream_branch = self._git_upstream_branch(repository_path)
        if upstream_branch:
            pull_args = ["pull", "--ff-only"]
        else:
            if not branch_name:
                QMessageBox.warning(
                    self,
                    "Git Pull",
                    "Cannot pull in detached HEAD state without an explicit branch.",
                )
                return
            remote_name = self._git_default_remote_for_branch(repository_path, branch_name)
            if not remote_name:
                QMessageBox.warning(
                    self,
                    "Git Pull",
                    "No remote configured for this repository.",
                )
                return
            pull_args = ["pull", "--ff-only", remote_name, branch_name]

        pull_ok = self._execute_git_command(
            repository_path,
            pull_args,
            action_label="pull",
            timeout_seconds=300,
            show_error_dialog=False,
        )
        if not pull_ok:
            fallback_answer = QMessageBox.question(
                self,
                "Pull Failed",
                "Fast-forward pull failed. Try `git pull --rebase` instead?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if fallback_answer == QMessageBox.StandardButton.Yes:
                pull_ok = self._execute_git_command(
                    repository_path,
                    ["pull", "--rebase"],
                    action_label="pull --rebase",
                    timeout_seconds=300,
                )

        if pull_ok:
            self._refresh_after_git_worktree_change()
        self._refresh_git_status_panel()

    def _git_push(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        has_local_changes, local_change_count = self._git_local_change_summary(repository_path)
        if has_local_changes:
            commit_message = self.git_commit_input.text().strip() if hasattr(self, "git_commit_input") else ""
            if commit_message:
                answer = QMessageBox.question(
                    self,
                    "Commit Local Changes",
                    (
                        f"You have {local_change_count} local change(s).\n\n"
                        "Commit all local changes with the current message, then push?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Cancel:
                    return
                if answer == QMessageBox.StandardButton.Yes and not self._git_commit_changes():
                    return
            else:
                answer = QMessageBox.question(
                    self,
                    "Push With Local Changes",
                    (
                        f"You have {local_change_count} local change(s) that are not committed.\n"
                        "These local changes will not be pushed.\n\n"
                        "Continue pushing existing commits?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

        branch_name = self._git_current_branch(repository_path)
        if not branch_name:
            QMessageBox.warning(
                self,
                "Git Push",
                "Cannot push in detached HEAD state.",
            )
            return

        upstream_branch = self._git_upstream_branch(repository_path)
        if upstream_branch:
            push_args = ["push"]
            action_label = "push"
        else:
            remote_name = self._git_default_remote_for_branch(repository_path, branch_name)
            if not remote_name:
                QMessageBox.warning(
                    self,
                    "Git Push",
                    "No remote configured for this repository.",
                )
                return
            push_args = ["push", "-u", remote_name, branch_name]
            action_label = f"push -u {remote_name} {branch_name}"

        self._execute_git_command(
            repository_path,
            push_args,
            action_label=action_label,
            timeout_seconds=300,
        )
        self._refresh_git_status_panel()

    def _git_sync(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        branch_name = self._git_current_branch(repository_path)
        if not branch_name:
            QMessageBox.warning(
                self,
                "Git Sync",
                "Cannot sync in detached HEAD state.",
            )
            self._refresh_git_status_panel()
            return

        upstream_branch = self._git_upstream_branch(repository_path)
        if upstream_branch:
            pull_ok = self._execute_git_command(
                repository_path,
                ["pull", "--ff-only"],
                action_label="sync(pull)",
                timeout_seconds=300,
                show_error_dialog=False,
            )
            if not pull_ok:
                fallback_answer = QMessageBox.question(
                    self,
                    "Sync Pull Failed",
                    "Fast-forward pull failed during sync. Try `git pull --rebase`?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if fallback_answer == QMessageBox.StandardButton.Yes:
                    pull_ok = self._execute_git_command(
                        repository_path,
                        ["pull", "--rebase"],
                        action_label="sync(pull --rebase)",
                        timeout_seconds=300,
                    )
            if not pull_ok:
                self._refresh_git_status_panel()
                return

            self._refresh_after_git_worktree_change()
            self._execute_git_command(
                repository_path,
                ["push"],
                action_label="sync(push)",
                timeout_seconds=300,
            )
        else:
            remote_name = self._git_default_remote_for_branch(repository_path, branch_name)
            if not remote_name:
                QMessageBox.warning(
                    self,
                    "Git Sync",
                    "No remote configured for this repository.",
                )
                self._refresh_git_status_panel()
                return
            self._execute_git_command(
                repository_path,
                ["push", "-u", remote_name, branch_name],
                action_label=f"sync(push -u {remote_name} {branch_name})",
                timeout_seconds=300,
            )
            self._refresh_after_git_worktree_change()
        self._refresh_git_status_panel()

    def _refresh_git_log(self) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            self.git_log_list.clear()
            return

        ok, stdout_text, stderr_text, _exit_code = self._run_git_command(
            repository_path,
            [
                "--no-pager",
                "log",
                f"-n{self._GIT_LOG_MAX_ENTRIES}",
                "--date=short",
                "--pretty=format:%h\t%ad\t%s\t%d",
            ],
            timeout_seconds=30,
        )
        self.git_log_list.clear()
        if not ok:
            message = stderr_text or "Could not load git log."
            self.git_log_list.addItem(message)
            return

        lines = [line for line in stdout_text.splitlines() if line.strip()]
        for line in lines:
            parts = line.split("\t", 3)
            if len(parts) < 3:
                item = QListWidgetItem(line)
                self.git_log_list.addItem(item)
                continue
            commit_hash = parts[0].strip()
            commit_date = parts[1].strip()
            subject = parts[2].strip()
            decoration = parts[3].strip() if len(parts) > 3 else ""
            text = f"{commit_hash}  {commit_date}  {subject}"
            if decoration:
                text = f"{text}  {decoration}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, commit_hash)
            item.setToolTip(text)
            self.git_log_list.addItem(item)

    def _on_git_log_activated(self, item: QListWidgetItem) -> None:
        repository_path = self._active_git_repository()
        if not repository_path:
            return

        commit_hash = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(commit_hash, str) or not commit_hash:
            return

        ok, stdout_text, stderr_text, _exit_code = self._run_git_command(
            repository_path,
            ["--no-pager", "show", "--stat", "--patch", "--color=never", commit_hash],
            timeout_seconds=40,
        )
        if ok:
            self.git_diff_view.setPlainText(stdout_text or f"No details for commit {commit_hash}.")
            return
        self.git_diff_view.setPlainText(stderr_text or f"Could not load commit {commit_hash}.")

    def _refresh_git_after_path_change(self, *, rescan_repositories: bool = False) -> None:
        if not hasattr(self, "git_repo_combo"):
            return
        if rescan_repositories:
            self._refresh_git_repositories()
            return
        if self._solution_nav_panel == "git" and self._active_git_repository():
            self._refresh_git_status_panel()

    def _update_solution_explorer_surface(self) -> None:
        if not hasattr(self, "solution_explorer_stack"):
            return

        if self.workspace_root and os.path.isdir(self.workspace_root):
            self.solution_explorer_stack.setCurrentWidget(self.file_tree)
        else:
            self.solution_explorer_stack.setCurrentWidget(self.solution_explorer_placeholder)
        self._refresh_solution_explorer_dock_title()

    def _build_output_dock(self) -> None:
        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setObjectName("outputDock")
        self.output_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )

        self.output_panel = QPlainTextEdit()
        self.output_panel.setReadOnly(True)
        self.output_panel.setObjectName("outputPanel")
        self.output_panel.setPlainText("Temcode output panel initialized.")
        self.output_panel.installEventFilter(self)

        self.output_dock.setWidget(self.output_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)
        self.output_toggle_action.setCheckable(True)
        self.output_toggle_action.setChecked(True)
        self.output_toggle_action.toggled.connect(self.output_dock.setVisible)
        self.output_dock.visibilityChanged.connect(self._on_output_dock_visibility_changed)
        self.output_dock.installEventFilter(self)

    def _build_terminal_dock(self) -> None:
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setObjectName("terminalDock")
        self.terminal_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )

        terminal_container = QWidget(self.terminal_dock)
        terminal_layout = QVBoxLayout(terminal_container)
        terminal_layout.setContentsMargins(8, 8, 8, 8)
        terminal_layout.setSpacing(6)

        self.terminal_console = CmdTerminalWidget(terminal_container)
        self.terminal_console.installEventFilter(self)
        self.terminal_console.session_started.connect(
            lambda cwd: self.log(f"[terminal] Started cmd.exe in {cwd}")
        )
        self.terminal_console.session_error.connect(
            lambda message: self.log(f"[terminal] {message}")
        )
        self.terminal_console.session_exited.connect(
            lambda exit_code: self.log(f"[terminal] cmd exited with code {exit_code}")
        )
        terminal_layout.addWidget(self.terminal_console, 1)

        self.terminal_dock.setWidget(terminal_container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self._set_bottom_dock_layout(persist=False)

        self.terminal_toggle_action.setCheckable(True)
        self.terminal_toggle_action.setChecked(True)
        self.terminal_toggle_action.toggled.connect(self.terminal_dock.setVisible)
        self.terminal_dock.visibilityChanged.connect(self._on_terminal_dock_visibility_changed)
        self.terminal_dock.installEventFilter(self)
        terminal_container.installEventFilter(self)

    def _set_bottom_dock_layout(self, persist: bool = True) -> None:
        self._bottom_layout_mode = self._BOTTOM_LAYOUT_SIDE_BY_SIDE
        if not hasattr(self, "output_dock") or not hasattr(self, "terminal_dock"):
            return

        orientation = Qt.Orientation.Horizontal
        self.splitDockWidget(self.output_dock, self.terminal_dock, orientation)
        self.resizeDocks([self.output_dock, self.terminal_dock], [1, 1], orientation)
        self._connect_splitter_move_persistence_hooks()
        if persist:
            self._persist_ui_settings()
        self.log("[layout] Bottom panels set to side by side.")

    def _on_output_dock_visibility_changed(self, is_visible: bool) -> None:
        self.output_toggle_action.blockSignals(True)
        self.output_toggle_action.setChecked(is_visible)
        self.output_toggle_action.blockSignals(False)
        if not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def _on_solution_explorer_dock_visibility_changed(self, is_visible: bool) -> None:
        self.solution_explorer_toggle_action.blockSignals(True)
        self.solution_explorer_toggle_action.setChecked(is_visible)
        self.solution_explorer_toggle_action.blockSignals(False)
        if is_visible and self._solution_nav_panel == "git":
            self._refresh_git_repositories()

    def _on_terminal_dock_visibility_changed(self, is_visible: bool) -> None:
        self.terminal_toggle_action.blockSignals(True)
        self.terminal_toggle_action.setChecked(is_visible)
        self.terminal_toggle_action.blockSignals(False)
        if not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802 (Qt API)
        if hasattr(self, "output_dock") and hasattr(self, "terminal_dock"):
            watch_targets = (
                self,
                self.output_dock,
                self.terminal_dock,
                self.output_dock.widget(),
                self.terminal_dock.widget(),
                self.terminal_console,
            )
            watch_event_types = {
                QEvent.Type.Resize,
                QEvent.Type.LayoutRequest,
                QEvent.Type.Show,
                QEvent.Type.Hide,
            }
            if any(watched is target for target in watch_targets if target is not None) and event.type() in watch_event_types:
                self._schedule_ui_settings_persistence()
        return super().eventFilter(watched, event)

    def _apply_pointing_cursor_to_buttons(self, root: QWidget | None) -> None:
        if root is None:
            return

        pointing_cursor = Qt.CursorShape.PointingHandCursor

        if isinstance(root, QAbstractButton):
            root.setCursor(pointing_cursor)
        if isinstance(root, QAbstractItemView):
            root.setCursor(pointing_cursor)
            root.viewport().setCursor(pointing_cursor)
        if isinstance(root, QComboBox):
            root.setCursor(pointing_cursor)
            popup_view = root.view()
            if popup_view is not None:
                popup_view.setCursor(pointing_cursor)
                popup_view.viewport().setCursor(pointing_cursor)
        if isinstance(root, QTabBar):
            root.setCursor(pointing_cursor)

        for button in root.findChildren(QAbstractButton):
            button.setCursor(pointing_cursor)
        for item_view in root.findChildren(QAbstractItemView):
            item_view.setCursor(pointing_cursor)
            item_view.viewport().setCursor(pointing_cursor)
        for combo_box in root.findChildren(QComboBox):
            combo_box.setCursor(pointing_cursor)
            popup_view = combo_box.view()
            if popup_view is not None:
                popup_view.setCursor(pointing_cursor)
                popup_view.viewport().setCursor(pointing_cursor)
        for tab_bar in root.findChildren(QTabBar):
            tab_bar.setCursor(pointing_cursor)

    def _schedule_ui_settings_persistence(self) -> None:
        if self._suspend_ui_settings_persistence or self._is_app_closing:
            return
        self._ui_settings_persist_timer.start()

    def _connect_splitter_move_persistence_hooks(self) -> None:
        for splitter in self.findChildren(QSplitter):
            splitter_id = id(splitter)
            if splitter_id in self._settings_persistence_splitter_ids:
                continue
            splitter.splitterMoved.connect(
                lambda _position, _index: self._schedule_ui_settings_persistence()
            )
            self._settings_persistence_splitter_ids.add(splitter_id)

    def open_file_dialog(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            start_dir,
            (
                "All Files (*.*);;"
                "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.ico)"
            ),
        )
        if file_path:
            self.open_file(file_path)

    def open_folder_dialog(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", start_dir)
        if folder:
            self.set_workspace_root(folder)

    def _create_file_from_welcome(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        parent_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose Folder for New File",
            start_dir,
        )
        if not parent_dir:
            return

        created_path = self._create_new_file(parent_dir)
        if created_path:
            self.open_file(created_path)

    def _create_folder_from_welcome(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        parent_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose Parent Folder",
            start_dir,
        )
        if not parent_dir:
            return

        created_path = self._create_new_folder(parent_dir)
        if created_path:
            self.set_workspace_root(created_path)

    def close_workspace(self) -> None:
        if not self._close_all_open_editors():
            return

        closed_workspace = self.workspace_root
        self.workspace_root = None
        self._settings_file_path = None

        root_index = self.fs_model.setRootPath("")
        self.file_tree.setRootIndex(root_index)
        self.setWindowTitle("Temcode")

        if self.terminal_console is not None:
            self.terminal_console.set_working_directory(os.getcwd())

        self._lsp_diagnostics_by_path.clear()
        self._lsp_client.stop()
        self._refresh_lsp_status_label()
        self._sync_file_watcher_paths()
        self._update_editor_mode_status(None)
        self._refresh_breadcrumbs(None)
        self._update_solution_explorer_surface()
        self._update_editor_surface()
        self._refresh_git_repositories(preserve_selection=False)

        if closed_workspace:
            self.log(f"[workspace] Closed folder: {closed_workspace}")
        else:
            self.log("[workspace] Closed current workspace context.")
        self.statusBar().showMessage("Workspace closed.", 2200)

    def set_workspace_root(self, folder_path: str, track_recent: bool = True) -> None:
        normalized = os.path.abspath(folder_path)
        index = self.fs_model.setRootPath(normalized)
        self.file_tree.setRootIndex(index)
        self.workspace_root = normalized
        self.setWindowTitle(f"Temcode - {normalized}")
        self.statusBar().showMessage(f"Workspace: {normalized}", 3000)
        self.log(f"[workspace] Opened folder: {normalized}")
        self._load_workspace_settings()
        self._load_recent_paths()
        if track_recent:
            self._record_recent_path(normalized)
        if self.terminal_console is not None:
            self.terminal_console.set_working_directory(normalized)
        self._lsp_client.stop()
        for editor in self._open_editors():
            self._schedule_lsp_document_sync(editor, immediate=True)
        self._sync_file_watcher_paths()
        self._refresh_breadcrumbs()
        self._update_solution_explorer_surface()
        self._update_editor_surface()
        self._refresh_git_repositories(preserve_selection=False)

    def _show_tree_context_menu(self, pos: QPoint) -> None:
        if not self.workspace_root:
            return

        index = self.file_tree.indexAt(pos)
        clicked_path = self.fs_model.filePath(index) if index.isValid() else self.workspace_root
        parent_dir = clicked_path if os.path.isdir(clicked_path) else os.path.dirname(clicked_path)

        menu = QMenu(self)
        new_file_action = menu.addAction("New File")
        new_folder_action = menu.addAction("New Folder")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        if not index.isValid():
            rename_action.setEnabled(False)
            delete_action.setEnabled(False)
        else:
            target_path = self.fs_model.filePath(index)
            if self._paths_equal(target_path, self.workspace_root):
                rename_action.setEnabled(False)
                delete_action.setEnabled(False)

        selected_action = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        if selected_action is None:
            return
        if selected_action == new_file_action:
            self._create_new_file(parent_dir)
        elif selected_action == new_folder_action:
            self._create_new_folder(parent_dir)
        elif selected_action == rename_action and index.isValid():
            self._rename_path(self.fs_model.filePath(index))
        elif selected_action == delete_action and index.isValid():
            self._delete_path(self.fs_model.filePath(index))

    def _show_tab_context_menu(self, tabs: QTabWidget, pos: QPoint) -> None:
        tab_index = tabs.tabBar().tabAt(pos)
        if tab_index < 0:
            return

        widget = self._tab_widget_at(tabs, tab_index)
        if widget is None:
            return

        file_path = self._widget_file_path(widget)
        menu = QMenu(self)
        move_action = menu.addAction("Move To Other Split")
        close_action = menu.addAction("Close")
        close_all_action = menu.addAction("Close All")
        menu.addSeparator()
        copy_path_action = menu.addAction("Copy Path")
        open_in_explorer_action = menu.addAction("Open in Explorer")

        has_file_path = bool(file_path)
        copy_path_action.setEnabled(has_file_path)
        open_in_explorer_action.setEnabled(has_file_path)

        selected = menu.exec(tabs.tabBar().mapToGlobal(pos))
        if selected == move_action:
            tabs.setCurrentIndex(tab_index)
            self._set_active_tab_widget(tabs)
            self.move_current_tab_to_other_split()
        elif selected == close_action:
            self._request_close_tab(tabs, tab_index)
        elif selected == close_all_action:
            self._set_active_tab_widget(tabs)
            self._close_all_open_editors()
        elif selected == copy_path_action and file_path:
            QApplication.clipboard().setText(os.path.abspath(file_path))
            self.statusBar().showMessage(f"Copied path: {os.path.abspath(file_path)}", 2500)
        elif selected == open_in_explorer_action and file_path:
            absolute_path = os.path.abspath(file_path)
            try:
                subprocess.Popen(["explorer", f"/select,{os.path.normpath(absolute_path)}"])
            except OSError as exc:
                self._show_error("Open in Explorer", absolute_path, exc)

    def new_file(self) -> None:
        display_name = f"Untitled-{self._untitled_counter}"
        self._untitled_counter += 1

        editor = self._create_editor_widget(
            "",
            file_path=None,
            display_name=display_name,
            large_file_mode=False,
            large_file_reason="",
        )
        target_tabs = self._active_editor_tabs or self.primary_tabs
        tab_index = self._add_editor_tab(target_tabs, editor, display_name)
        target_tabs.setTabToolTip(tab_index, display_name)
        target_tabs.setCurrentIndex(tab_index)
        self._set_active_tab_widget(target_tabs)
        self._update_editor_surface()
        editor.setFocus()
        self._update_editor_mode_status(editor)
        self._refresh_breadcrumbs(editor)
        self.log(f"[editor] New file: {display_name}")

    def _create_new_file(self, parent_dir: str) -> str | None:
        file_name, ok = QInputDialog.getText(self, "New File", "File name:")
        if not ok:
            return None

        file_name = file_name.strip()
        if not file_name:
            return None

        full_path = os.path.join(parent_dir, file_name)
        if os.path.exists(full_path):
            QMessageBox.warning(self, "Create File", f"A file or folder already exists:\n{full_path}")
            return None

        try:
            with open(full_path, "x", encoding="utf-8"):
                pass
            self.log(f"[file] Created file: {full_path}")
            self._reveal_path(full_path)
            self._refresh_git_after_path_change()
            return full_path
        except OSError as exc:
            self._show_error("Create File", full_path, exc)
            return None

    def _create_new_folder(self, parent_dir: str) -> str | None:
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok:
            return None

        folder_name = folder_name.strip()
        if not folder_name:
            return None

        full_path = os.path.join(parent_dir, folder_name)
        if os.path.exists(full_path):
            QMessageBox.warning(self, "Create Folder", f"A file or folder already exists:\n{full_path}")
            return None

        try:
            os.mkdir(full_path)
            self.log(f"[file] Created folder: {full_path}")
            self._reveal_path(full_path)
            self._refresh_git_after_path_change(rescan_repositories=True)
            return full_path
        except OSError as exc:
            self._show_error("Create Folder", full_path, exc)
            return None

    def _rename_path(self, old_path: str) -> None:
        if self.workspace_root and self._paths_equal(old_path, self.workspace_root):
            QMessageBox.information(self, "Rename", "Renaming the workspace root is not supported.")
            return

        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return

        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Rename", f"Target already exists:\n{new_path}")
            return

        try:
            os.rename(old_path, new_path)
            self.log(f"[file] Renamed: {old_path} -> {new_path}")
            self._update_open_tabs_after_rename(old_path, new_path)
            self._reveal_path(new_path)
            self._refresh_git_after_path_change(rescan_repositories=True)
        except OSError as exc:
            self._show_error("Rename", old_path, exc)

    def _delete_path(self, target_path: str) -> None:
        if self.workspace_root and self._paths_equal(target_path, self.workspace_root):
            QMessageBox.information(self, "Delete", "Deleting the workspace root is not supported.")
            return

        label = "folder" if os.path.isdir(target_path) else "file"
        answer = QMessageBox.question(
            self,
            "Delete",
            f"Delete this {label}?\n{target_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            self.log(f"[file] Deleted {label}: {target_path}")
            self._close_tabs_for_deleted_path(target_path)
            self._refresh_git_after_path_change(rescan_repositories=True)
        except OSError as exc:
            self._show_error("Delete", target_path, exc)

    def _on_tree_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            self.open_file(path)

    def open_file(self, file_path: str) -> None:
        absolute_path = os.path.abspath(file_path)
        self._ensure_workspace_for_file(absolute_path)

        if self._is_image_file_path(absolute_path):
            self._open_image_file(absolute_path)
            return

        key = self._normalize_path(absolute_path)

        existing_editor = self._open_editors_by_path.get(key)
        if existing_editor is not None:
            tab_widget = self._find_tab_widget_for_editor(existing_editor)
            if tab_widget is not None:
                tab_widget.setCurrentWidget(existing_editor)
                self._set_active_tab_widget(tab_widget)
                self._reveal_path(absolute_path)
                self._update_editor_mode_status(existing_editor)
                self._refresh_breadcrumbs(existing_editor)
                self._apply_lsp_diagnostics_to_editor(existing_editor)
                self._record_file_disk_state(absolute_path)
                self._record_recent_path(absolute_path)
                self._schedule_lsp_document_sync(existing_editor, immediate=True)
                self._update_editor_surface()
                existing_editor.setFocus()
                return
            self._open_editors_by_path.pop(key, None)

        try:
            content = self._read_text_file(absolute_path)
        except OSError as exc:
            self._show_error("Open File", absolute_path, exc)
            return

        large_file_mode, large_file_reason = self._evaluate_large_file_mode(absolute_path, content)
        editor = self._create_editor_widget(
            content,
            file_path=absolute_path,
            display_name=os.path.basename(absolute_path),
            large_file_mode=large_file_mode,
            large_file_reason=large_file_reason,
        )

        target_tabs = self._active_editor_tabs or self.primary_tabs
        tab_index = self._add_editor_tab(target_tabs, editor, "")
        target_tabs.setCurrentIndex(tab_index)
        self._set_active_tab_widget(target_tabs)

        self._open_editors_by_path[key] = editor
        self._record_file_disk_state(absolute_path)
        self._record_recent_path(absolute_path)
        self._sync_file_watcher_paths()
        self._update_editor_tab_title(editor)
        self.statusBar().showMessage(f"Opened {absolute_path}", 2500)
        self.log(f"[editor] Opened file: {absolute_path}")
        if large_file_mode:
            self.log(f"[editor] Large File Mode enabled for {os.path.basename(absolute_path)} ({large_file_reason})")
        self._reveal_path(absolute_path)
        self._update_editor_surface()
        self._update_editor_mode_status(editor)
        self._refresh_breadcrumbs(editor)
        self._apply_lsp_diagnostics_to_editor(editor)
        self._schedule_lsp_document_sync(editor, immediate=True)

    def _open_image_file(self, file_path: str) -> None:
        absolute_path = os.path.abspath(file_path)
        key = self._normalize_path(absolute_path)

        existing_viewer = self._open_image_tabs_by_path.get(key)
        if existing_viewer is not None:
            tab_widget = self._find_tab_widget_for_editor(existing_viewer)
            if tab_widget is not None:
                tab_widget.setCurrentWidget(existing_viewer)
                self._set_active_tab_widget(tab_widget)
                self._reveal_path(absolute_path)
                self._update_editor_mode_status(existing_viewer)
                self._refresh_breadcrumbs(existing_viewer)
                self._record_file_disk_state(absolute_path)
                self._record_recent_path(absolute_path)
                self._update_editor_surface()
                existing_viewer.setFocus()
                return
            self._open_image_tabs_by_path.pop(key, None)

        viewer = ImageViewer(absolute_path, self)
        if not viewer.reload_image():
            QMessageBox.warning(self, "Open Image", f"Could not decode image:\n{absolute_path}")
            return

        self._apply_pointing_cursor_to_buttons(viewer)
        viewer.setProperty("file_path", absolute_path)
        viewer.setProperty("display_name", os.path.basename(absolute_path))

        target_tabs = self._active_editor_tabs or self.primary_tabs
        tab_index = self._add_editor_tab(target_tabs, viewer, os.path.basename(absolute_path))
        target_tabs.setCurrentIndex(tab_index)
        self._set_active_tab_widget(target_tabs)

        self._open_image_tabs_by_path[key] = viewer
        self._record_file_disk_state(absolute_path)
        self._record_recent_path(absolute_path)
        self._sync_file_watcher_paths()
        self._update_editor_tab_title(viewer)
        self.statusBar().showMessage(f"Opened image {absolute_path}", 2500)
        self.log(f"[viewer] Opened image: {absolute_path}")
        self._reveal_path(absolute_path)
        self._update_editor_surface()
        self._update_editor_mode_status(viewer)
        self._refresh_breadcrumbs(viewer)
        viewer.setFocus()

    @classmethod
    def _is_image_file_path(cls, file_path: str) -> bool:
        extension = os.path.splitext(file_path)[1].lower()
        return extension in cls._IMAGE_FILE_EXTENSIONS

    def _ensure_workspace_for_file(self, file_path: str) -> None:
        absolute_path = os.path.abspath(file_path)
        parent_dir = os.path.dirname(absolute_path)
        if not parent_dir or not os.path.isdir(parent_dir):
            return

        if self.workspace_root:
            if self._is_same_or_child(absolute_path, self.workspace_root):
                return
            if self._paths_equal(self.workspace_root, parent_dir):
                return

        self.set_workspace_root(parent_dir)

    def open_find_panel(self, show_replace: bool) -> None:
        self.find_panel.show()
        self._set_replace_controls_visible(show_replace)

        editor = self._current_editor()
        if editor is not None:
            selected_text = editor.textCursor().selectedText().replace("\u2029", "\n")
            if selected_text and "\n" not in selected_text:
                self.find_input.setText(selected_text)
            self.find_input.selectAll()

        self.find_input.setFocus()
        self._refresh_find_highlights()

    def close_find_panel(self) -> None:
        self.find_panel.hide()
        self._clear_find_highlights()

    def _set_replace_controls_visible(self, is_visible: bool) -> None:
        self.replace_label.setVisible(is_visible)
        self.replace_input.setVisible(is_visible)
        self.replace_button.setVisible(is_visible)
        self.replace_all_button.setVisible(is_visible)

    def _on_find_text_changed(self, _text: str) -> None:
        self._refresh_find_highlights()

    def _refresh_find_highlights(self) -> None:
        editor = self._current_editor()
        query = self.find_input.text()

        if self._find_highlight_editor is not None and self._find_highlight_editor is not editor:
            self._find_highlight_editor.set_external_extra_selections([])
            self._find_highlight_editor = None

        if editor is None or not self.find_panel.isVisible() or not query:
            if editor is not None:
                editor.set_external_extra_selections([])
            self._find_highlight_editor = editor
            return

        selections: list[QTextEdit.ExtraSelection] = []
        scan_cursor = QTextCursor(editor.document())
        scan_cursor.setPosition(0)
        max_highlights = 300

        while len(selections) < max_highlights:
            found = editor.document().find(query, scan_cursor)
            if found.isNull():
                break

            selection = QTextEdit.ExtraSelection()
            selection.cursor = found
            selection.format.setBackground(Qt.GlobalColor.darkYellow)
            selection.format.setForeground(Qt.GlobalColor.black)
            selections.append(selection)
            scan_cursor = found

        editor.set_external_extra_selections(selections)
        self._find_highlight_editor = editor

    def _clear_find_highlights(self) -> None:
        if self._find_highlight_editor is not None:
            self._find_highlight_editor.set_external_extra_selections([])
            self._find_highlight_editor = None

    def find_next(self) -> None:
        self._find_in_active_editor(backward=False)

    def find_previous(self) -> None:
        self._find_in_active_editor(backward=True)

    def _find_in_active_editor(self, backward: bool) -> bool:
        editor = self._current_editor()
        query = self.find_input.text()
        if editor is None or not query:
            return False

        flags = QTextDocument.FindFlags()
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward

        start_cursor = editor.textCursor()
        found = editor.document().find(query, start_cursor, flags)
        if found.isNull():
            wrapped_cursor = QTextCursor(editor.document())
            if backward:
                wrapped_cursor.setPosition(max(0, editor.document().characterCount() - 1))
            else:
                wrapped_cursor.setPosition(0)
            found = editor.document().find(query, wrapped_cursor, flags)

        if found.isNull():
            self.statusBar().showMessage(f"No matches for '{query}'", 2500)
            return False

        editor.setTextCursor(found)
        editor.centerCursor()
        self.statusBar().showMessage(f"Found '{query}'", 1200)
        return True

    def replace_current(self) -> None:
        editor = self._current_editor()
        query = self.find_input.text()
        if editor is None or not query:
            return

        cursor = editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        if selected_text != query:
            if not self._find_in_active_editor(backward=False):
                return
            cursor = editor.textCursor()
            selected_text = cursor.selectedText().replace("\u2029", "\n")
            if selected_text != query:
                return

        cursor.insertText(self.replace_input.text())
        editor.setTextCursor(cursor)
        self._refresh_find_highlights()
        self.find_next()

    def replace_all(self) -> None:
        editor = self._current_editor()
        query = self.find_input.text()
        if editor is None or not query:
            return

        replacement = self.replace_input.text()
        replace_count = 0

        transaction_cursor = QTextCursor(editor.document())
        transaction_cursor.beginEditBlock()

        scan_cursor = QTextCursor(editor.document())
        scan_cursor.setPosition(0)

        while True:
            found = editor.document().find(query, scan_cursor)
            if found.isNull():
                break

            found.insertText(replacement)
            replace_count += 1
            scan_cursor = found

        transaction_cursor.endEditBlock()
        self._refresh_find_highlights()
        self.statusBar().showMessage(f"Replaced {replace_count} occurrence(s).", 2500)
        self.log(f"[find] Replaced {replace_count} occurrence(s) of '{query}'.")

    def save_current_file(self) -> bool:
        editor = self._current_editor()
        if editor is None:
            active_widget = self._current_tab_widget()
            if isinstance(active_widget, ImageViewer):
                self.statusBar().showMessage("Image tabs are read-only.", 2200)
            return False
        return self._save_editor(editor, save_as=False)

    def save_current_file_as(self) -> bool:
        editor = self._current_editor()
        if editor is None:
            active_widget = self._current_tab_widget()
            if isinstance(active_widget, ImageViewer):
                self.statusBar().showMessage("Image tabs are read-only.", 2200)
            return False
        return self._save_editor(editor, save_as=True)

    def _save_editor(self, editor: CodeEditor, save_as: bool) -> bool:
        current_path = self._editor_file_path(editor)
        target_path = current_path

        if save_as or not target_path:
            base_dir = self.workspace_root or os.getcwd()
            if target_path:
                base_dir = os.path.dirname(target_path)
            suggested_name = os.path.basename(target_path) if target_path else self._editor_display_name(editor)
            suggested_path = os.path.join(base_dir, suggested_name)
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save File As" if save_as or not target_path else "Save File",
                suggested_path,
                "All Files (*.*)",
            )
            if not selected_path:
                return False
            target_path = selected_path

        absolute_target = os.path.abspath(target_path)
        target_key = self._normalize_path(absolute_target)

        existing_editor = self._open_editors_by_path.get(target_key)
        if existing_editor is not None and existing_editor is not editor:
            QMessageBox.warning(
                self,
                "Save File",
                f"Cannot save to this path because it is already open in another tab:\n{absolute_target}",
            )
            return False
        existing_viewer = self._open_image_tabs_by_path.get(target_key)
        if existing_viewer is not None:
            QMessageBox.warning(
                self,
                "Save File",
                f"Cannot save to this path because it is open as an image tab:\n{absolute_target}",
            )
            return False

        try:
            with open(absolute_target, "w", encoding="utf-8", newline="") as handle:
                handle.write(editor.toPlainText())
        except OSError as exc:
            self._show_error("Save File", absolute_target, exc)
            return False

        self._mark_internal_write(absolute_target)
        if current_path:
            self._open_editors_by_path.pop(self._normalize_path(current_path), None)
            if not self._paths_equal(current_path, absolute_target):
                self._file_disk_state.pop(self._normalize_path(current_path), None)
                self._lsp_client.close_document(current_path)
                self._clear_lsp_diagnostics_for_path(current_path)
        editor.setProperty("file_path", absolute_target)
        self._open_editors_by_path[target_key] = editor
        self._record_file_disk_state(absolute_target)
        self._record_recent_path(absolute_target)
        self._sync_file_watcher_paths()
        large_file_mode, large_file_reason = self._evaluate_large_file_mode(absolute_target, editor.toPlainText())
        editor.configure_syntax_highlighting(absolute_target, large_file_mode)
        editor.setProperty("large_file_mode", large_file_mode)
        editor.setProperty("large_file_mode_reason", large_file_reason)
        editor.document().setModified(False)
        self._update_editor_tab_title(editor)
        self._reveal_path(absolute_target)
        self._update_editor_mode_status(editor)
        self._refresh_breadcrumbs(editor)
        self._schedule_lsp_document_sync(editor, immediate=True)
        self._apply_lsp_diagnostics_to_editor(editor)
        self.statusBar().showMessage(f"Saved {absolute_target}", 2500)
        self.log(f"[editor] Saved file: {absolute_target}")
        if large_file_mode:
            self.log(f"[editor] Large File Mode active ({large_file_reason})")
        self._refresh_git_after_path_change()
        return True

    def _create_editor_widget(
        self,
        content: str,
        file_path: str | None,
        display_name: str,
        large_file_mode: bool,
        large_file_reason: str,
    ) -> CodeEditor:
        editor = CodeEditor(self)
        editor.set_theme(self._theme_id)
        editor.setPlainText(content)
        editor.document().setModified(False)
        editor.setProperty("file_path", os.path.abspath(file_path) if file_path else None)
        editor.setProperty("display_name", display_name)
        editor.setProperty("large_file_mode", large_file_mode)
        editor.setProperty("large_file_mode_reason", large_file_reason)
        editor.setProperty("autosave_token", f"editor-{id(editor):x}")
        editor.configure_syntax_highlighting(file_path, large_file_mode)
        self._apply_code_zoom_to_editor(editor)
        editor.document().modificationChanged.connect(lambda _v, e=editor: self._update_editor_tab_title(e))
        editor.textChanged.connect(lambda e=editor: self._on_editor_text_changed(e))
        editor.code_zoom_changed.connect(lambda point_size, e=editor: self._on_editor_code_zoom_changed(e, point_size))
        editor.destroyed.connect(lambda _obj=None, key=id(editor): self._cleanup_lsp_timer(key))
        return editor

    def _clamp_code_zoom_point_size(self, point_size: float) -> float:
        return max(
            self._MIN_CODE_ZOOM_POINT_SIZE,
            min(self._MAX_CODE_ZOOM_POINT_SIZE, float(point_size)),
        )

    def _apply_code_zoom_to_editor(self, editor: CodeEditor) -> None:
        if self._code_zoom_point_size is None:
            return
        editor.set_code_zoom_point_size(self._code_zoom_point_size, emit_signal=False)

    def _apply_code_zoom_to_open_editors(self, source_editor: CodeEditor | None = None) -> None:
        if self._code_zoom_point_size is None:
            return
        for editor in self._open_editors():
            if source_editor is not None and editor is source_editor:
                continue
            editor.set_code_zoom_point_size(self._code_zoom_point_size, emit_signal=False)

    def _on_editor_code_zoom_changed(self, source_editor: CodeEditor, point_size: float) -> None:
        self._code_zoom_point_size = self._clamp_code_zoom_point_size(point_size)
        self._apply_code_zoom_to_open_editors(source_editor=source_editor)
        if not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def _on_editor_text_changed(self, editor: CodeEditor) -> None:
        if self.find_panel.isVisible() and editor is self._current_editor():
            self._refresh_find_highlights()
        self._schedule_lsp_document_sync(editor)

    def _evaluate_large_file_mode(self, file_path: str | None, content: str) -> tuple[bool, str]:
        size_bytes = len(content.encode("utf-8", errors="ignore"))
        if file_path:
            try:
                size_bytes = os.path.getsize(file_path)
            except OSError:
                pass

        line_count = content.count("\n") + (1 if content else 0)
        reasons: list[str] = []

        if size_bytes >= self._LARGE_FILE_SIZE_THRESHOLD_BYTES:
            reasons.append(f"{size_bytes:,} bytes")
        if line_count >= self._LARGE_FILE_LINE_THRESHOLD:
            reasons.append(f"{line_count:,} lines")

        return bool(reasons), ", ".join(reasons)

    def _update_editor_mode_status(self, widget: QWidget | None) -> None:
        if widget is None:
            self.language_status_label.setText("Plain Text")
            self.large_file_status_label.setText("")
            self.large_file_status_label.setToolTip("")
            self._refresh_lsp_status_label()
            return

        if isinstance(widget, ImageViewer):
            dimensions = widget.image_dimensions_text()
            self.language_status_label.setText("Image")
            self.large_file_status_label.setText(dimensions)
            self.large_file_status_label.setToolTip(widget.file_path())
            self._refresh_lsp_status_label()
            return

        if isinstance(widget, CodeEditor):
            self.language_status_label.setText(widget.language_display_name())
            if widget.is_large_file_mode():
                reason_value = widget.property("large_file_mode_reason")
                reason = reason_value if isinstance(reason_value, str) else ""
                self.large_file_status_label.setText("Large File Mode")
                self.large_file_status_label.setToolTip(reason or "Large file optimizations enabled.")
            else:
                self.large_file_status_label.setText("")
                self.large_file_status_label.setToolTip("")
            self._refresh_lsp_status_label()
            return

        self.language_status_label.setText("Plain Text")
        self.large_file_status_label.setText("")
        self.large_file_status_label.setToolTip("")
        self._refresh_lsp_status_label()

    def _lsp_workspace_root(self, editor: CodeEditor | None = None) -> str:
        if self.workspace_root and os.path.isdir(self.workspace_root):
            return os.path.abspath(self.workspace_root)

        if editor is not None:
            editor_path = self._editor_file_path(editor)
            if editor_path:
                parent_dir = os.path.dirname(os.path.abspath(editor_path))
                if os.path.isdir(parent_dir):
                    return parent_dir

        return os.getcwd()

    def _should_use_lsp_for_editor(self, editor: CodeEditor | None) -> bool:
        if editor is None:
            return False
        if editor.language_id() != LanguageId.PYTHON:
            return False
        if editor.is_large_file_mode():
            return False
        file_path = self._editor_file_path(editor)
        return isinstance(file_path, str) and bool(file_path)

    def _cleanup_lsp_timer(self, editor_key: int) -> None:
        self._lsp_document_timers.pop(editor_key, None)

    def _lsp_sync_timer_for_editor(self, editor: CodeEditor) -> QTimer:
        editor_key = id(editor)
        timer = self._lsp_document_timers.get(editor_key)
        if timer is not None:
            return timer

        timer = QTimer(editor)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda e=editor: self._sync_editor_document_with_lsp(e))
        self._lsp_document_timers[editor_key] = timer
        return timer

    def _ensure_lsp_ready_for_editor(self, editor: CodeEditor) -> bool:
        workspace_root = self._lsp_workspace_root(editor)
        if not self._lsp_client.ensure_started(workspace_root):
            self._refresh_lsp_status_label()
            return False
        return True

    def _schedule_lsp_document_sync(self, editor: CodeEditor, immediate: bool = False) -> None:
        if not self._should_use_lsp_for_editor(editor):
            editor.set_diagnostic_extra_selections([])
            self._refresh_lsp_status_label()
            return

        timer = self._lsp_sync_timer_for_editor(editor)
        if immediate:
            timer.stop()
            self._sync_editor_document_with_lsp(editor)
            return

        timer.start(self._LSP_DID_CHANGE_DEBOUNCE_MS)

    def _sync_editor_document_with_lsp(self, editor: CodeEditor) -> None:
        if not self._should_use_lsp_for_editor(editor):
            return
        if not self._ensure_lsp_ready_for_editor(editor):
            return

        file_path = self._editor_file_path(editor)
        if not file_path:
            return

        self._lsp_client.open_or_change_document(file_path, editor.toPlainText(), language_id="python")

    def _close_lsp_document(self, editor: CodeEditor) -> None:
        file_path = self._editor_file_path(editor)
        if file_path:
            self._lsp_client.close_document(file_path)
        editor.set_diagnostic_extra_selections([])
        self._refresh_lsp_status_label()

    def _clear_lsp_diagnostics_for_path(self, file_path: str) -> None:
        normalized_key = self._normalize_path(file_path)
        self._lsp_diagnostics_by_path.pop(normalized_key, None)

        for editor in self._open_editors():
            editor_path = self._editor_file_path(editor)
            if editor_path and self._normalize_path(editor_path) == normalized_key:
                editor.set_diagnostic_extra_selections([])

        self._refresh_lsp_status_label()

    def _on_lsp_ready_changed(self, ready: bool, status_message: str) -> None:
        self._lsp_ready = ready
        self._lsp_status_message = status_message

        if not ready:
            self._lsp_diagnostics_by_path.clear()
            for editor in self._open_editors():
                editor.set_diagnostic_extra_selections([])
            self._refresh_lsp_status_label()
            return

        for editor in self._open_editors():
            self._schedule_lsp_document_sync(editor, immediate=True)
            self._apply_lsp_diagnostics_to_editor(editor)
        self._refresh_lsp_status_label()

    def _on_lsp_diagnostics_published(self, uri: str, diagnostics_payload: object) -> None:
        file_path = uri_to_path(uri)
        if not file_path:
            return

        normalized_key = self._normalize_path(file_path)
        if isinstance(diagnostics_payload, list):
            diagnostics = [entry for entry in diagnostics_payload if isinstance(entry, dict)]
        else:
            diagnostics = []
        self._lsp_diagnostics_by_path[normalized_key] = diagnostics

        for editor in self._open_editors():
            editor_path = self._editor_file_path(editor)
            if editor_path and self._normalize_path(editor_path) == normalized_key:
                self._apply_lsp_diagnostics_to_editor(editor)

        self._refresh_lsp_status_label()

    def _apply_lsp_diagnostics_to_editor(self, editor: CodeEditor) -> None:
        if not self._should_use_lsp_for_editor(editor):
            editor.set_diagnostic_extra_selections([])
            self._refresh_lsp_status_label()
            return

        file_path = self._editor_file_path(editor)
        if not file_path:
            editor.set_diagnostic_extra_selections([])
            self._refresh_lsp_status_label()
            return

        diagnostics = self._lsp_diagnostics_by_path.get(self._normalize_path(file_path), [])
        selections = self._build_lsp_diagnostic_selections(editor, diagnostics)
        editor.set_diagnostic_extra_selections(selections)
        self._refresh_lsp_status_label()

    def _build_lsp_diagnostic_selections(
        self,
        editor: CodeEditor,
        diagnostics: list[dict[str, object]],
    ) -> list[QTextEdit.ExtraSelection]:
        selections: list[QTextEdit.ExtraSelection] = []
        max_position = max(0, editor.document().characterCount() - 1)

        for diagnostic in diagnostics[: self._LSP_MAX_DIAGNOSTIC_SELECTIONS]:
            range_payload = diagnostic.get("range")
            if not isinstance(range_payload, dict):
                continue

            severity_value = diagnostic.get("severity")
            try:
                severity = int(severity_value) if severity_value is not None else 2
            except (TypeError, ValueError):
                severity = 2

            message_value = diagnostic.get("message")
            message = message_value if isinstance(message_value, str) else ""
            cursor = self._range_to_cursor(editor, range_payload)

            if not cursor.hasSelection() and max_position > 0:
                anchor = min(max(0, cursor.position()), max_position - 1)
                cursor.setPosition(anchor)
                cursor.setPosition(anchor + 1, QTextCursor.MoveMode.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            selection.format.setUnderlineColor(self._diagnostic_color_for_severity(severity))
            if message:
                selection.format.setToolTip(message)
            selections.append(selection)

        return selections

    def _cursor_to_lsp_position(self, editor: CodeEditor) -> tuple[int, int]:
        cursor = editor.textCursor()
        block = cursor.block()
        line = max(0, block.blockNumber())
        character = max(0, cursor.position() - block.position())
        return line, character

    def _lsp_position_to_cursor_offset(self, editor: CodeEditor, line: int, character: int) -> int:
        normalized_line = max(0, int(line))
        normalized_character = max(0, int(character))
        document = editor.document()

        block = document.findBlockByNumber(normalized_line)
        if not block.isValid():
            block = document.lastBlock()
            if not block.isValid():
                return 0

        line_text = block.text()
        clamped_character = min(normalized_character, len(line_text))
        return block.position() + clamped_character

    def _range_to_cursor(self, editor: CodeEditor, range_payload: dict[str, object]) -> QTextCursor:
        start_payload = range_payload.get("start")
        end_payload = range_payload.get("end")
        if not isinstance(start_payload, dict):
            return editor.textCursor()
        if not isinstance(end_payload, dict):
            end_payload = start_payload

        try:
            start_line = int(start_payload.get("line", 0))
            start_character = int(start_payload.get("character", 0))
            end_line = int(end_payload.get("line", start_line))
            end_character = int(end_payload.get("character", start_character))
        except (TypeError, ValueError):
            return editor.textCursor()

        start_position = self._lsp_position_to_cursor_offset(editor, start_line, start_character)
        end_position = self._lsp_position_to_cursor_offset(editor, end_line, end_character)
        if end_position < start_position:
            start_position, end_position = end_position, start_position

        cursor = QTextCursor(editor.document())
        cursor.setPosition(start_position)
        cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
        return cursor

    @staticmethod
    def _diagnostic_color_for_severity(severity: int) -> QColor:
        if severity == 1:
            return QColor("#ff5f56")
        if severity == 2:
            return QColor("#f0c674")
        if severity == 3:
            return QColor("#6cb6ff")
        return QColor("#8b949e")

    def _diagnostic_summary_for_editor(self, editor: CodeEditor | None) -> str:
        if editor is None or not self._should_use_lsp_for_editor(editor):
            return "idle"

        file_path = self._editor_file_path(editor)
        if not file_path:
            return "idle"

        diagnostics = self._lsp_diagnostics_by_path.get(self._normalize_path(file_path), [])
        if not diagnostics:
            return "clean"

        errors = 0
        warnings = 0
        infos = 0
        hints = 0
        for diagnostic in diagnostics:
            severity_value = diagnostic.get("severity")
            try:
                severity = int(severity_value)
            except (TypeError, ValueError):
                severity = 2
            if severity == 1:
                errors += 1
            elif severity == 2:
                warnings += 1
            elif severity == 3:
                infos += 1
            else:
                hints += 1

        parts: list[str] = []
        if errors:
            parts.append(f"{errors}E")
        if warnings:
            parts.append(f"{warnings}W")
        if infos:
            parts.append(f"{infos}I")
        if hints:
            parts.append(f"{hints}H")
        return " ".join(parts) if parts else "clean"

    def _refresh_lsp_status_label(self) -> None:
        if not hasattr(self, "lsp_status_label"):
            return

        if not self._lsp_ready:
            self.lsp_status_label.setText(f"LSP: {self._lsp_status_message}")
            self.lsp_status_label.setToolTip(
                "Python language server status. Install python-lsp-server, pyright-langserver, or jedi-language-server."
            )
            return

        summary = self._diagnostic_summary_for_editor(self._current_editor())
        self.lsp_status_label.setText(f"LSP: {summary}")
        self.lsp_status_label.setToolTip(self._lsp_status_message)

    def _editor_by_id(self, editor_id: int) -> CodeEditor | None:
        for editor in self._open_editors():
            if id(editor) == editor_id:
                return editor
        return None

    def trigger_lsp_completion(self) -> None:
        editor = self._current_editor()
        if not self._should_use_lsp_for_editor(editor):
            self.statusBar().showMessage("Completion is available for saved Python files.", 2500)
            return
        assert editor is not None
        if not self._ensure_lsp_ready_for_editor(editor):
            self.statusBar().showMessage("Python LSP server is unavailable.", 2800)
            return

        file_path = self._editor_file_path(editor)
        if not file_path:
            return

        self._schedule_lsp_document_sync(editor, immediate=True)
        line, character = self._cursor_to_lsp_position(editor)
        self._lsp_client.request_completion(
            file_path,
            line,
            character,
            lambda result, error, editor_id=id(editor): self._show_lsp_completion_menu(editor_id, result, error),
        )

    def _show_lsp_completion_menu(
        self,
        editor_id: int,
        result: object | None,
        error: dict[str, object] | None,
    ) -> None:
        editor = self._editor_by_id(editor_id)
        if editor is None:
            return

        if error is not None:
            message = error.get("message") if isinstance(error.get("message"), str) else "Completion request failed."
            self.statusBar().showMessage(message, 3000)
            self.log(f"[lsp] Completion error: {error}")
            return

        items: list[dict[str, object]] = []
        if isinstance(result, list):
            items = [entry for entry in result if isinstance(entry, dict)]
        elif isinstance(result, dict):
            result_items = result.get("items")
            if isinstance(result_items, list):
                items = [entry for entry in result_items if isinstance(entry, dict)]

        if not items:
            self.statusBar().showMessage("No completion items.", 1200)
            return

        menu = QMenu(editor)
        added_items = 0
        for item in items[: self._LSP_MAX_COMPLETION_ITEMS]:
            label_value = item.get("label")
            if not isinstance(label_value, str):
                continue
            label = label_value.strip()
            if not label:
                continue

            detail_value = item.get("detail")
            detail = detail_value.strip() if isinstance(detail_value, str) else ""
            action_text = label if not detail else f"{label}    {detail}"
            action = menu.addAction(action_text)
            action.triggered.connect(lambda _checked=False, e=editor, completion=item: self._apply_completion_item(e, completion))
            added_items += 1

        if added_items <= 0:
            self.statusBar().showMessage("No completion items.", 1200)
            return

        if len(items) > self._LSP_MAX_COMPLETION_ITEMS:
            menu.addSeparator()
            more_action = menu.addAction(f"...and {len(items) - self._LSP_MAX_COMPLETION_ITEMS} more")
            more_action.setEnabled(False)

        popup_position = editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft())
        menu.exec(popup_position)

    def _apply_completion_item(self, editor: CodeEditor, item: dict[str, object]) -> None:
        insert_text = self._completion_insert_text(item)
        if not insert_text:
            return

        cursor = editor.textCursor()
        text_edit_payload = item.get("textEdit")
        if isinstance(text_edit_payload, dict):
            if isinstance(text_edit_payload.get("range"), dict):
                cursor = self._range_to_cursor(editor, text_edit_payload["range"])
                replacement_value = text_edit_payload.get("newText")
                if isinstance(replacement_value, str):
                    insert_text = replacement_value
            elif isinstance(text_edit_payload.get("replace"), dict):
                cursor = self._range_to_cursor(editor, text_edit_payload["replace"])
                replacement_value = text_edit_payload.get("newText")
                if isinstance(replacement_value, str):
                    insert_text = replacement_value
        else:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)

        cursor.insertText(insert_text)
        editor.setTextCursor(cursor)
        self._schedule_lsp_document_sync(editor)

    def _completion_insert_text(self, item: dict[str, object]) -> str:
        insert_value = item.get("insertText")
        if isinstance(insert_value, str) and insert_value:
            insert_text = insert_value
        else:
            label_value = item.get("label")
            insert_text = label_value if isinstance(label_value, str) else ""

        if item.get("insertTextFormat") == 2:
            return self._sanitize_snippet_text(insert_text)
        return insert_text

    @staticmethod
    def _sanitize_snippet_text(text: str) -> str:
        cleaned = re.sub(r"\$\{(\d+):([^}]*)\}", r"\2", text)
        cleaned = re.sub(r"\$\{(\d+)\}", "", cleaned)
        cleaned = re.sub(r"\$(\d+)", "", cleaned)
        return cleaned.replace("\\$", "$")

    def go_to_definition(self) -> None:
        editor = self._current_editor()
        if not self._should_use_lsp_for_editor(editor):
            self.statusBar().showMessage("Go-to-definition is available for saved Python files.", 2500)
            return
        assert editor is not None
        if not self._ensure_lsp_ready_for_editor(editor):
            self.statusBar().showMessage("Python LSP server is unavailable.", 2800)
            return

        file_path = self._editor_file_path(editor)
        if not file_path:
            return

        self._schedule_lsp_document_sync(editor, immediate=True)
        line, character = self._cursor_to_lsp_position(editor)
        self._lsp_client.request_definition(
            file_path,
            line,
            character,
            lambda result, error, editor_id=id(editor): self._handle_go_to_definition_result(editor_id, result, error),
        )

    def _handle_go_to_definition_result(
        self,
        editor_id: int,
        result: object | None,
        error: dict[str, object] | None,
    ) -> None:
        if self._editor_by_id(editor_id) is None:
            return

        if error is not None:
            message = error.get("message") if isinstance(error.get("message"), str) else "Go-to-definition failed."
            self.statusBar().showMessage(message, 3200)
            self.log(f"[lsp] Definition error: {error}")
            return

        location = self._extract_location_from_result(result)
        if location is None:
            self.statusBar().showMessage("No definition found.", 1800)
            return

        uri_value = location.get("uri")
        if not isinstance(uri_value, str):
            self.statusBar().showMessage("No definition found.", 1800)
            return

        target_path = uri_to_path(uri_value)
        if not target_path:
            self.statusBar().showMessage("Definition location could not be resolved.", 2500)
            return

        range_payload = location.get("range")
        if not isinstance(range_payload, dict):
            range_payload = {}
        start_payload = range_payload.get("start")
        if not isinstance(start_payload, dict):
            start_payload = {}

        try:
            line = int(start_payload.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        try:
            character = int(start_payload.get("character", 0))
        except (TypeError, ValueError):
            character = 0

        self._jump_to_file_location(target_path, line, character)

    def _extract_location_from_result(self, result: object | None) -> dict[str, object] | None:
        if isinstance(result, dict):
            uri_value = result.get("uri")
            if isinstance(uri_value, str):
                range_value = result.get("range")
                if not isinstance(range_value, dict):
                    range_value = {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}
                return {"uri": uri_value, "range": range_value}

            target_uri = result.get("targetUri")
            if isinstance(target_uri, str):
                target_range = result.get("targetSelectionRange")
                if not isinstance(target_range, dict):
                    target_range = result.get("targetRange")
                if not isinstance(target_range, dict):
                    target_range = {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}
                return {"uri": target_uri, "range": target_range}
            return None

        if isinstance(result, list):
            for item in result:
                resolved = self._extract_location_from_result(item)
                if resolved is not None:
                    return resolved
        return None

    def _jump_to_editor_location(self, editor: CodeEditor, line: int, character: int) -> None:
        tab_widget = self._find_tab_widget_for_editor(editor)
        if tab_widget is not None:
            tab_index = tab_widget.indexOf(editor)
            if tab_index >= 0:
                tab_widget.setCurrentIndex(tab_index)
                self._set_active_tab_widget(tab_widget)

        safe_line = max(0, int(line))
        safe_character = max(0, int(character))
        target_offset = self._lsp_position_to_cursor_offset(editor, safe_line, safe_character)
        cursor = editor.textCursor()
        cursor.setPosition(max(0, target_offset))
        editor.setTextCursor(cursor)
        editor.centerCursor()
        editor.setFocus()

    def _jump_to_file_location(self, file_path: str, line: int, character: int) -> None:
        self.open_file(file_path)
        key = self._normalize_path(file_path)
        editor = self._open_editors_by_path.get(key)
        if editor is None:
            return

        self._jump_to_editor_location(editor, line, character)
        self.statusBar().showMessage(f"Definition: {file_path}:{line + 1}", 2600)

    def rename_symbol(self) -> None:
        editor = self._current_editor()
        if not self._should_use_lsp_for_editor(editor):
            self.statusBar().showMessage("Rename is available for saved Python files.", 2500)
            return
        assert editor is not None
        if not self._ensure_lsp_ready_for_editor(editor):
            self.statusBar().showMessage("Python LSP server is unavailable.", 2800)
            return

        file_path = self._editor_file_path(editor)
        if not file_path:
            return

        cursor = editor.textCursor()
        current_symbol = cursor.selectedText().replace("\u2029", "\n").strip()
        if not current_symbol:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            current_symbol = cursor.selectedText().replace("\u2029", "\n").strip()

        new_name, ok = QInputDialog.getText(self, "Rename Symbol", "New name:", text=current_symbol)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        self._schedule_lsp_document_sync(editor, immediate=True)
        line, character = self._cursor_to_lsp_position(editor)
        self._lsp_client.request_rename(
            file_path,
            line,
            character,
            new_name,
            self._apply_rename_result,
        )

    def _apply_rename_result(self, result: object | None, error: dict[str, object] | None) -> None:
        if error is not None:
            message = error.get("message") if isinstance(error.get("message"), str) else "Rename request failed."
            self.statusBar().showMessage(message, 3200)
            self.log(f"[lsp] Rename error: {error}")
            return

        if not isinstance(result, dict):
            self.statusBar().showMessage("No rename changes were produced.", 2200)
            return

        changed_files, changed_edits = self._apply_workspace_edit(result)
        if changed_files <= 0:
            self.statusBar().showMessage("No rename edits to apply.", 2200)
            return

        self.statusBar().showMessage(
            f"Rename applied: {changed_edits} edit(s) across {changed_files} file(s).",
            3200,
        )
        self.log(f"[lsp] Rename applied: {changed_edits} edit(s) across {changed_files} file(s).")

    def _apply_workspace_edit(self, workspace_edit: dict[str, object]) -> tuple[int, int]:
        collected_changes = self._collect_workspace_edit_changes(workspace_edit)
        if not collected_changes:
            return 0, 0

        changed_files = 0
        changed_edits = 0
        for file_path, edits in collected_changes.items():
            if not edits:
                continue

            key = self._normalize_path(file_path)
            open_editor = self._open_editors_by_path.get(key)
            if open_editor is not None:
                applied = self._apply_text_edits_to_editor(open_editor, edits)
            else:
                applied = self._apply_text_edits_to_file(file_path, edits)

            if applied > 0:
                changed_files += 1
                changed_edits += applied
                self._record_file_disk_state(file_path)

        if changed_files > 0:
            self._sync_file_watcher_paths()
            self._refresh_git_after_path_change()
        return changed_files, changed_edits

    def _collect_workspace_edit_changes(self, workspace_edit: dict[str, object]) -> dict[str, list[dict[str, object]]]:
        collected: dict[str, list[dict[str, object]]] = {}

        changes_payload = workspace_edit.get("changes")
        if isinstance(changes_payload, dict):
            for uri, edits_payload in changes_payload.items():
                if not isinstance(uri, str) or not isinstance(edits_payload, list):
                    continue
                resolved_path = uri_to_path(uri)
                if not resolved_path:
                    continue
                valid_edits = [entry for entry in edits_payload if isinstance(entry, dict)]
                if not valid_edits:
                    continue
                collected.setdefault(os.path.abspath(resolved_path), []).extend(valid_edits)

        document_changes = workspace_edit.get("documentChanges")
        if isinstance(document_changes, list):
            for change in document_changes:
                if not isinstance(change, dict):
                    continue
                text_document = change.get("textDocument")
                edits_payload = change.get("edits")
                if not isinstance(text_document, dict) or not isinstance(edits_payload, list):
                    continue
                uri_value = text_document.get("uri")
                if not isinstance(uri_value, str):
                    continue
                resolved_path = uri_to_path(uri_value)
                if not resolved_path:
                    continue
                valid_edits = [entry for entry in edits_payload if isinstance(entry, dict)]
                if not valid_edits:
                    continue
                collected.setdefault(os.path.abspath(resolved_path), []).extend(valid_edits)

        return collected

    @staticmethod
    def _sort_text_edits_descending(edits: list[dict[str, object]]) -> list[dict[str, object]]:
        def sort_key(edit: dict[str, object]) -> tuple[int, int]:
            range_payload = edit.get("range")
            if not isinstance(range_payload, dict):
                return (0, 0)
            start_payload = range_payload.get("start")
            if not isinstance(start_payload, dict):
                return (0, 0)
            try:
                line = int(start_payload.get("line", 0))
            except (TypeError, ValueError):
                line = 0
            try:
                character = int(start_payload.get("character", 0))
            except (TypeError, ValueError):
                character = 0
            return (line, character)

        return sorted(edits, key=sort_key, reverse=True)

    def _apply_text_edits_to_editor(self, editor: CodeEditor, edits: list[dict[str, object]]) -> int:
        sorted_edits = self._sort_text_edits_descending(edits)
        if not sorted_edits:
            return 0

        block_cursor = QTextCursor(editor.document())
        block_cursor.beginEditBlock()
        applied_count = 0
        try:
            for edit in sorted_edits:
                range_payload = edit.get("range")
                if not isinstance(range_payload, dict):
                    continue
                start_payload = range_payload.get("start")
                end_payload = range_payload.get("end")
                if not isinstance(start_payload, dict) or not isinstance(end_payload, dict):
                    continue

                try:
                    start_line = int(start_payload.get("line", 0))
                    start_character = int(start_payload.get("character", 0))
                    end_line = int(end_payload.get("line", start_line))
                    end_character = int(end_payload.get("character", start_character))
                except (TypeError, ValueError):
                    continue

                start_position = self._lsp_position_to_cursor_offset(editor, start_line, start_character)
                end_position = self._lsp_position_to_cursor_offset(editor, end_line, end_character)
                if end_position < start_position:
                    start_position, end_position = end_position, start_position

                replacement_value = edit.get("newText")
                replacement_text = replacement_value if isinstance(replacement_value, str) else ""

                replacement_cursor = QTextCursor(editor.document())
                replacement_cursor.setPosition(start_position)
                replacement_cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
                replacement_cursor.insertText(replacement_text)
                applied_count += 1
        finally:
            block_cursor.endEditBlock()

        if applied_count > 0:
            self._update_editor_tab_title(editor)
            self._schedule_lsp_document_sync(editor, immediate=True)
        return applied_count

    def _apply_text_edits_to_file(self, file_path: str, edits: list[dict[str, object]]) -> int:
        if not os.path.isfile(file_path):
            return 0

        try:
            content = self._read_text_file(file_path)
        except OSError as exc:
            self.log(f"[lsp] Could not read rename target {file_path}: {exc}")
            return 0

        sorted_edits = self._sort_text_edits_descending(edits)
        if not sorted_edits:
            return 0

        applied_count = 0
        for edit in sorted_edits:
            range_payload = edit.get("range")
            if not isinstance(range_payload, dict):
                continue
            start_payload = range_payload.get("start")
            end_payload = range_payload.get("end")
            if not isinstance(start_payload, dict) or not isinstance(end_payload, dict):
                continue

            try:
                start_line = int(start_payload.get("line", 0))
                start_character = int(start_payload.get("character", 0))
                end_line = int(end_payload.get("line", start_line))
                end_character = int(end_payload.get("character", start_character))
            except (TypeError, ValueError):
                continue

            start_position = self._text_position_from_lsp(content, start_line, start_character)
            end_position = self._text_position_from_lsp(content, end_line, end_character)
            if end_position < start_position:
                start_position, end_position = end_position, start_position

            replacement_value = edit.get("newText")
            replacement_text = replacement_value if isinstance(replacement_value, str) else ""
            content = content[:start_position] + replacement_text + content[end_position:]
            applied_count += 1

        if applied_count <= 0:
            return 0

        try:
            with open(file_path, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
        except OSError as exc:
            self.log(f"[lsp] Could not write rename target {file_path}: {exc}")
            return 0

        self.log(f"[lsp] Updated file from rename: {file_path}")
        return applied_count

    @staticmethod
    def _text_position_from_lsp(content: str, line: int, character: int) -> int:
        normalized_line = max(0, int(line))
        normalized_character = max(0, int(character))

        lines = content.splitlines(keepends=True)
        if not lines:
            return 0
        if normalized_line >= len(lines):
            return len(content)

        offset = 0
        for index in range(normalized_line):
            offset += len(lines[index])

        line_text = lines[normalized_line]
        line_without_newline = line_text.rstrip("\r\n")
        offset += min(normalized_character, len(line_without_newline))
        return offset

    def open_settings_dialog(self) -> None:
        settings_path = self._workspace_settings_path()
        payload: dict[str, object] = self._default_settings_payload()

        try:
            self._ensure_workspace_settings_file(settings_path)
            with open(settings_path, "r", encoding="utf-8") as handle:
                parsed_payload = json.load(handle)
            if isinstance(parsed_payload, dict):
                payload = parsed_payload
            else:
                self.log("[settings] Root JSON must be an object; opening dialog with defaults.")
        except OSError as exc:
            self.log(f"[settings] Could not read {settings_path} for settings dialog: {exc}")
        except json.JSONDecodeError as exc:
            self.log(f"[settings] Invalid JSON in {settings_path}; opening dialog with defaults: {exc}")

        autosave_payload = payload.get("autosave")
        if not isinstance(autosave_payload, dict):
            autosave_payload = {}
        strategy_value = autosave_payload.get("strategy")
        autosave_strategy = strategy_value.strip() if isinstance(strategy_value, str) else ""
        if not autosave_strategy:
            autosave_strategy = "backup"

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            ui_payload = {}

        output_enabled_value = ui_payload.get("output_enabled")
        initial_output_enabled = output_enabled_value if isinstance(output_enabled_value, bool) else self.output_dock.isVisible()

        terminal_enabled_value = ui_payload.get("terminal_enabled")
        initial_terminal_enabled = (
            terminal_enabled_value
            if isinstance(terminal_enabled_value, bool)
            else self.terminal_dock.isVisible()
        )

        window_payload = ui_payload.get("window")
        if not isinstance(window_payload, dict):
            window_payload = {}

        use_last_size_value = window_payload.get("use_last_size")
        initial_window_use_last_size = use_last_size_value if isinstance(use_last_size_value, bool) else False

        def _parse_dimension(value: object, minimum: int, fallback: int) -> int:
            if isinstance(value, bool):
                return fallback
            try:
                parsed_value = int(value)
            except (TypeError, ValueError):
                return fallback
            return max(minimum, parsed_value)

        initial_window_width = _parse_dimension(
            window_payload.get("width"),
            self._MIN_WINDOW_WIDTH,
            max(self._MIN_WINDOW_WIDTH, int(self.width())),
        )
        initial_window_height = _parse_dimension(
            window_payload.get("height"),
            self._MIN_WINDOW_HEIGHT,
            max(self._MIN_WINDOW_HEIGHT, int(self.height())),
        )
        initial_python_interpreter = self._parse_python_interpreter_setting(payload) or (
            self._python_interpreter_path or ""
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setModal(True)
        dialog.resize(840, 580)
        dialog.setMinimumSize(760, 520)

        layout = QVBoxLayout(dialog)
        tabs = QTabWidget(dialog)
        layout.addWidget(tabs, 1)

        appearance_tab = QWidget(dialog)
        appearance_form = QFormLayout(appearance_tab)
        appearance_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        theme_combobox = QComboBox(dialog)
        for theme_id in available_theme_ids():
            theme_combobox.addItem(theme_display_name(theme_id), theme_id)
        current_theme_index = theme_combobox.findData(self._theme_id)
        if current_theme_index >= 0:
            theme_combobox.setCurrentIndex(current_theme_index)

        ui_zoom_spinbox = QSpinBox(dialog)
        ui_zoom_spinbox.setRange(self._MIN_UI_ZOOM_PERCENT, self._MAX_UI_ZOOM_PERCENT)
        ui_zoom_spinbox.setValue(self._ui_zoom_percent)
        ui_zoom_spinbox.setSuffix(" %")

        code_zoom_fallback = self._code_zoom_point_size
        if code_zoom_fallback is None:
            current_editor = self._current_editor()
            code_zoom_fallback = current_editor.code_zoom_point_size() if current_editor is not None else 10.0
        code_zoom_fallback = self._clamp_code_zoom_point_size(code_zoom_fallback)

        code_zoom_override_checkbox = QCheckBox("Override editor font size", dialog)
        code_zoom_override_checkbox.setChecked(self._code_zoom_point_size is not None)

        code_zoom_spinbox = QDoubleSpinBox(dialog)
        code_zoom_spinbox.setRange(self._MIN_CODE_ZOOM_POINT_SIZE, self._MAX_CODE_ZOOM_POINT_SIZE)
        code_zoom_spinbox.setSingleStep(0.5)
        code_zoom_spinbox.setDecimals(1)
        code_zoom_spinbox.setValue(code_zoom_fallback)
        code_zoom_spinbox.setSuffix(" pt")
        code_zoom_spinbox.setEnabled(self._code_zoom_point_size is not None)
        code_zoom_override_checkbox.toggled.connect(code_zoom_spinbox.setEnabled)

        appearance_form.addRow("Theme", theme_combobox)
        appearance_form.addRow("UI zoom", ui_zoom_spinbox)
        appearance_form.addRow(code_zoom_override_checkbox)
        appearance_form.addRow("Code zoom", code_zoom_spinbox)
        tabs.addTab(appearance_tab, "Appearance")

        behavior_tab = QWidget(dialog)
        behavior_layout = QVBoxLayout(behavior_tab)
        behavior_layout.setContentsMargins(0, 0, 0, 0)
        behavior_layout.setSpacing(10)

        autosave_form = QFormLayout()
        autosave_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        autosave_enabled_checkbox = QCheckBox("Enable autosave backups", dialog)
        autosave_enabled_checkbox.setChecked(self._autosave_enabled)

        autosave_interval_spinbox = QSpinBox(dialog)
        autosave_interval_spinbox.setRange(
            self._MIN_AUTOSAVE_INTERVAL_SECONDS,
            self._MAX_AUTOSAVE_INTERVAL_SECONDS,
        )
        autosave_interval_spinbox.setValue(self._autosave_interval_seconds)
        autosave_interval_spinbox.setSuffix(" s")
        autosave_interval_spinbox.setEnabled(self._autosave_enabled)
        autosave_enabled_checkbox.toggled.connect(autosave_interval_spinbox.setEnabled)

        autosave_strategy_combobox = QComboBox(dialog)
        autosave_strategy_combobox.setEditable(True)
        autosave_strategy_combobox.addItem("backup")
        if autosave_strategy.lower() != "backup":
            autosave_strategy_combobox.addItem(autosave_strategy)
        autosave_strategy_combobox.setCurrentText(autosave_strategy)

        autosave_form.addRow("Autosave", autosave_enabled_checkbox)
        autosave_form.addRow("Interval", autosave_interval_spinbox)
        autosave_form.addRow("Strategy", autosave_strategy_combobox)

        panels_form = QFormLayout()
        panels_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        output_enabled_checkbox = QCheckBox("Show Output panel", dialog)
        output_enabled_checkbox.setChecked(initial_output_enabled)

        terminal_enabled_checkbox = QCheckBox("Show Terminal panel", dialog)
        terminal_enabled_checkbox.setChecked(initial_terminal_enabled)

        panels_form.addRow("Output", output_enabled_checkbox)
        panels_form.addRow("Terminal", terminal_enabled_checkbox)

        panels_separator = QFrame(behavior_tab)
        panels_separator.setFrameShape(QFrame.Shape.HLine)
        panels_separator.setFrameShadow(QFrame.Shadow.Sunken)

        behavior_layout.addLayout(autosave_form)
        behavior_layout.addWidget(panels_separator)
        behavior_layout.addLayout(panels_form)
        behavior_layout.addStretch(1)
        tabs.addTab(behavior_tab, "Behavior")

        startup_tab = QWidget(dialog)
        startup_layout = QVBoxLayout(startup_tab)
        startup_layout.setContentsMargins(0, 0, 0, 0)
        startup_layout.setSpacing(8)

        startup_note_label = QLabel(
            "Window size settings are applied the next time Temcode starts.",
            startup_tab,
        )
        startup_note_label.setWordWrap(True)
        startup_layout.addWidget(startup_note_label)

        startup_form = QFormLayout()
        startup_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        window_use_last_size_checkbox = QCheckBox("Restore last/custom size on startup", dialog)
        window_use_last_size_checkbox.setChecked(initial_window_use_last_size)

        window_width_spinbox = QSpinBox(dialog)
        window_width_spinbox.setRange(self._MIN_WINDOW_WIDTH, 9999)
        window_width_spinbox.setValue(initial_window_width)
        window_width_spinbox.setSuffix(" px")

        window_height_spinbox = QSpinBox(dialog)
        window_height_spinbox.setRange(self._MIN_WINDOW_HEIGHT, 9999)
        window_height_spinbox.setValue(initial_window_height)
        window_height_spinbox.setSuffix(" px")

        window_width_spinbox.setEnabled(initial_window_use_last_size)
        window_height_spinbox.setEnabled(initial_window_use_last_size)
        window_use_last_size_checkbox.toggled.connect(window_width_spinbox.setEnabled)
        window_use_last_size_checkbox.toggled.connect(window_height_spinbox.setEnabled)

        startup_form.addRow("Startup mode", window_use_last_size_checkbox)
        startup_form.addRow("Window width", window_width_spinbox)
        startup_form.addRow("Window height", window_height_spinbox)
        startup_layout.addLayout(startup_form)
        startup_layout.addStretch(1)
        tabs.addTab(startup_tab, "Startup")

        python_tab = QWidget(dialog)
        python_layout = QVBoxLayout(python_tab)
        python_layout.setContentsMargins(0, 0, 0, 0)
        python_layout.setSpacing(8)

        python_form = QFormLayout()
        python_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        interpreter_row = QWidget(dialog)
        interpreter_row_layout = QHBoxLayout(interpreter_row)
        interpreter_row_layout.setContentsMargins(0, 0, 0, 0)
        interpreter_row_layout.setSpacing(6)

        python_interpreter_input = QLineEdit(dialog)
        python_interpreter_input.setPlaceholderText(r"C:\Python311\python.exe")
        python_interpreter_input.setText(initial_python_interpreter)

        browse_python_interpreter_button = QPushButton("Browse...", dialog)
        clear_python_interpreter_button = QPushButton("Clear", dialog)

        def _browse_python_interpreter() -> None:
            start_path = python_interpreter_input.text().strip()
            if not start_path:
                start_path = self.workspace_root or os.getcwd()
            selected_path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Select Python Interpreter",
                start_path,
                "Python Executable (python.exe);;All Files (*.*)",
            )
            if selected_path:
                python_interpreter_input.setText(os.path.abspath(selected_path))

        browse_python_interpreter_button.clicked.connect(_browse_python_interpreter)
        clear_python_interpreter_button.clicked.connect(lambda: python_interpreter_input.clear())

        interpreter_row_layout.addWidget(python_interpreter_input, 1)
        interpreter_row_layout.addWidget(browse_python_interpreter_button)
        interpreter_row_layout.addWidget(clear_python_interpreter_button)

        python_hint_label = QLabel(
            "Used by the Run button on Python files.",
            python_tab,
        )
        python_hint_label.setWordWrap(True)

        python_form.addRow("Interpreter", interpreter_row)
        python_layout.addLayout(python_form)
        python_layout.addWidget(python_hint_label)
        python_layout.addStretch(1)
        tabs.addTab(python_tab, "Python")

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        self._apply_pointing_cursor_to_buttons(dialog)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        selected_theme_data = theme_combobox.currentData()
        selected_theme_id = normalize_theme_id(selected_theme_data if isinstance(selected_theme_data, str) else None)

        selected_ui_zoom = max(
            self._MIN_UI_ZOOM_PERCENT,
            min(self._MAX_UI_ZOOM_PERCENT, int(ui_zoom_spinbox.value())),
        )
        selected_code_zoom = (
            self._clamp_code_zoom_point_size(code_zoom_spinbox.value())
            if code_zoom_override_checkbox.isChecked()
            else None
        )
        selected_autosave_strategy = autosave_strategy_combobox.currentText().strip() or "backup"
        selected_window_use_last_size = window_use_last_size_checkbox.isChecked()
        selected_window_width = max(self._MIN_WINDOW_WIDTH, int(window_width_spinbox.value()))
        selected_window_height = max(self._MIN_WINDOW_HEIGHT, int(window_height_spinbox.value()))
        selected_python_interpreter = python_interpreter_input.text().strip() or None

        self._suspend_ui_settings_persistence = True
        try:
            self._apply_theme(selected_theme_id)
            self._set_ui_zoom_percent(selected_ui_zoom, persist=False)
            self._code_zoom_point_size = selected_code_zoom
            if selected_code_zoom is not None:
                self._apply_code_zoom_to_open_editors()

            self._autosave_enabled = autosave_enabled_checkbox.isChecked()
            self._autosave_interval_seconds = max(
                self._MIN_AUTOSAVE_INTERVAL_SECONDS,
                min(self._MAX_AUTOSAVE_INTERVAL_SECONDS, int(autosave_interval_spinbox.value())),
            )
            self._autosave_last_summary = ""
            self._configure_autosave_timer()

            self._apply_bottom_layout_setting(self._BOTTOM_LAYOUT_SIDE_BY_SIDE)
            self._apply_bottom_panel_visibility_settings(
                output_enabled_checkbox.isChecked(),
                terminal_enabled_checkbox.isChecked(),
            )
            self._python_interpreter_path = selected_python_interpreter
            self._refresh_breadcrumbs()
        finally:
            self._suspend_ui_settings_persistence = False

        if self._persist_settings_preferences(
            autosave_strategy=selected_autosave_strategy,
            window_use_last_size=selected_window_use_last_size,
            window_width=selected_window_width,
            window_height=selected_window_height,
            python_interpreter=selected_python_interpreter,
        ):
            self.statusBar().showMessage("Settings saved.", 2200)
            self.log(
                f"[settings] Preferences updated: theme={self._theme_id}, ui_zoom={self._ui_zoom_percent}%, "
                f"code_zoom={self._code_zoom_point_size}, "
                f"autosave_enabled={self._autosave_enabled}, "
                f"autosave_interval={self._autosave_interval_seconds}s, "
                f"autosave_strategy={selected_autosave_strategy}, "
                f"layout={self._bottom_layout_mode}, "
                f"output_visible={self.output_dock.isVisible()}, terminal_visible={self.terminal_dock.isVisible()}, "
                f"python_interpreter={selected_python_interpreter}, "
                f"window_use_last_size={selected_window_use_last_size}, "
                f"window={selected_window_width}x{selected_window_height}"
            )
        else:
            self.statusBar().showMessage("Applied settings, but failed to write settings file.", 3200)

    def _adjust_ui_zoom(self, step_direction: int) -> None:
        if step_direction == 0:
            return
        target_zoom = self._ui_zoom_percent + (step_direction * self._UI_ZOOM_STEP_PERCENT)
        self._set_ui_zoom_percent(target_zoom)

    def _reset_ui_zoom(self) -> None:
        self._set_ui_zoom_percent(self._DEFAULT_UI_ZOOM_PERCENT)

    def _set_ui_zoom_percent(self, zoom_percent: int, persist: bool = True) -> None:
        clamped_zoom = max(self._MIN_UI_ZOOM_PERCENT, min(self._MAX_UI_ZOOM_PERCENT, int(zoom_percent)))
        if clamped_zoom == self._ui_zoom_percent:
            self._update_ui_zoom_actions()
            self.statusBar().showMessage(f"UI Zoom: {self._ui_zoom_percent}%", 1800)
            return

        self._ui_zoom_percent = clamped_zoom
        self._apply_theme(self._theme_id)
        self._update_ui_zoom_actions()
        self.statusBar().showMessage(f"UI Zoom: {self._ui_zoom_percent}%", 1800)

        if persist and not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def _update_ui_zoom_actions(self) -> None:
        if not hasattr(self, "zoom_in_ui_action") or not hasattr(self, "zoom_out_ui_action"):
            return
        self.zoom_in_ui_action.setEnabled(self._ui_zoom_percent < self._MAX_UI_ZOOM_PERCENT)
        self.zoom_out_ui_action.setEnabled(self._ui_zoom_percent > self._MIN_UI_ZOOM_PERCENT)

    def _apply_theme(self, theme_id: str | None) -> None:
        normalized_theme = normalize_theme_id(theme_id)
        self._theme_id = normalized_theme
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme_stylesheet_for(normalized_theme, self._ui_zoom_percent))
        for editor in self._open_editors():
            editor.set_theme(normalized_theme)
        self._refresh_tab_close_button_sizes()
        self._refresh_solution_nav_button_sizes()

    def _workspace_settings_dir(self) -> str:
        source_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        return os.path.join(source_root, self._SETTINGS_DIR_NAME)

    def _workspace_settings_path(self) -> str:
        return os.path.join(self._workspace_settings_dir(), self._SETTINGS_FILE_NAME)

    def _default_settings_payload(self) -> dict[str, object]:
        return {
            "autosave": {
                "enabled": self._DEFAULT_AUTOSAVE_ENABLED,
                "interval_seconds": self._DEFAULT_AUTOSAVE_INTERVAL_SECONDS,
                "strategy": "backup",
            },
            "ui": {
                "theme": self._DEFAULT_THEME_ID,
                "zoom_percent": self._DEFAULT_UI_ZOOM_PERCENT,
                "code_zoom_point_size": None,
                "bottom_panel_layout": self._BOTTOM_LAYOUT_SIDE_BY_SIDE,
                "output_enabled": True,
                "terminal_enabled": True,
                "terminal_height": None,
                "window": {
                    "use_last_size": False,
                },
            },
            "python": {
                "interpreter": "",
            },
        }

    def _ensure_workspace_settings_file(self, settings_path: str) -> None:
        settings_dir = os.path.dirname(settings_path)
        os.makedirs(settings_dir, exist_ok=True)
        if os.path.exists(settings_path):
            return

        with open(settings_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(self._default_settings_payload(), handle, indent=2)
            handle.write("\n")
        self.log(f"[settings] Created {settings_path}")

    def _parse_autosave_settings(self, payload: object) -> tuple[bool, int]:
        enabled = self._DEFAULT_AUTOSAVE_ENABLED
        interval_seconds = self._DEFAULT_AUTOSAVE_INTERVAL_SECONDS

        if not isinstance(payload, dict):
            self.log("[settings] Root JSON must be an object; using autosave defaults.")
            return enabled, interval_seconds

        autosave_payload = payload.get("autosave")
        if not isinstance(autosave_payload, dict):
            return enabled, interval_seconds

        enabled_value = autosave_payload.get("enabled")
        if isinstance(enabled_value, bool):
            enabled = enabled_value

        interval_value = autosave_payload.get("interval_seconds")
        if interval_value is not None:
            try:
                parsed_interval = int(interval_value)
                interval_seconds = max(
                    self._MIN_AUTOSAVE_INTERVAL_SECONDS,
                    min(self._MAX_AUTOSAVE_INTERVAL_SECONDS, parsed_interval),
                )
            except (TypeError, ValueError):
                self.log("[settings] Invalid autosave.interval_seconds; using default interval.")

        return enabled, interval_seconds

    def _parse_bottom_layout_setting(self, payload: object) -> str:
        if not isinstance(payload, dict):
            return self._BOTTOM_LAYOUT_SIDE_BY_SIDE

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return self._BOTTOM_LAYOUT_SIDE_BY_SIDE

        layout_value = ui_payload.get("bottom_panel_layout")
        if layout_value == self._BOTTOM_LAYOUT_SIDE_BY_SIDE:
            return self._BOTTOM_LAYOUT_SIDE_BY_SIDE
        if layout_value == "stacked":
            self.log("[settings] ui.bottom_panel_layout=stacked is deprecated; using side_by_side.")
            return self._BOTTOM_LAYOUT_SIDE_BY_SIDE

        if layout_value is not None:
            self.log("[settings] Invalid ui.bottom_panel_layout; using side_by_side.")
        return self._BOTTOM_LAYOUT_SIDE_BY_SIDE

    def _parse_theme_setting(self, payload: object) -> str:
        if not isinstance(payload, dict):
            return self._DEFAULT_THEME_ID

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return self._DEFAULT_THEME_ID

        theme_value = ui_payload.get("theme")
        if isinstance(theme_value, str):
            return normalize_theme_id(theme_value)
        if theme_value is not None:
            self.log("[settings] Invalid ui.theme; using default theme.")
        return self._DEFAULT_THEME_ID

    def _parse_ui_zoom_setting(self, payload: object) -> int:
        if not isinstance(payload, dict):
            return self._DEFAULT_UI_ZOOM_PERCENT

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return self._DEFAULT_UI_ZOOM_PERCENT

        zoom_value = ui_payload.get("zoom_percent")
        if zoom_value is None:
            return self._DEFAULT_UI_ZOOM_PERCENT

        try:
            parsed_zoom = int(zoom_value)
        except (TypeError, ValueError):
            self.log("[settings] Invalid ui.zoom_percent; using default zoom.")
            return self._DEFAULT_UI_ZOOM_PERCENT

        clamped_zoom = max(self._MIN_UI_ZOOM_PERCENT, min(self._MAX_UI_ZOOM_PERCENT, parsed_zoom))
        if clamped_zoom != parsed_zoom:
            self.log("[settings] ui.zoom_percent out of bounds; clamped to supported range.")
        return clamped_zoom

    def _parse_code_zoom_setting(self, payload: object) -> float | None:
        if not isinstance(payload, dict):
            return None

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return None

        zoom_value = ui_payload.get("code_zoom_point_size")
        if zoom_value is None:
            return None

        try:
            parsed_zoom = float(zoom_value)
        except (TypeError, ValueError):
            self.log("[settings] Invalid ui.code_zoom_point_size; using default editor zoom.")
            return None

        clamped_zoom = self._clamp_code_zoom_point_size(parsed_zoom)
        if abs(clamped_zoom - parsed_zoom) >= 1e-6:
            self.log("[settings] ui.code_zoom_point_size out of bounds; clamped to supported range.")
        return clamped_zoom

    def _parse_python_interpreter_setting(self, payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None

        python_payload = payload.get("python")
        if python_payload is None:
            return None
        if not isinstance(python_payload, dict):
            self.log("[settings] Invalid python section; using empty interpreter.")
            return None

        interpreter_value = python_payload.get("interpreter")
        if interpreter_value is None:
            return None
        if not isinstance(interpreter_value, str):
            self.log("[settings] Invalid python.interpreter; using empty interpreter.")
            return None

        normalized = interpreter_value.strip()
        return normalized or None

    def _parse_bottom_panel_visibility_settings(self, payload: object) -> tuple[bool, bool]:
        output_enabled = self.output_dock.isVisible() if hasattr(self, "output_dock") else True
        terminal_enabled = self.terminal_dock.isVisible() if hasattr(self, "terminal_dock") else True

        if not isinstance(payload, dict):
            return output_enabled, terminal_enabled

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return output_enabled, terminal_enabled

        output_value = ui_payload.get("output_enabled")
        if isinstance(output_value, bool):
            output_enabled = output_value
        elif output_value is not None:
            self.log("[settings] Invalid ui.output_enabled; keeping current state.")

        terminal_value = ui_payload.get("terminal_enabled")
        if isinstance(terminal_value, bool):
            terminal_enabled = terminal_value
        elif terminal_value is not None:
            self.log("[settings] Invalid ui.terminal_enabled; keeping current state.")

        return output_enabled, terminal_enabled

    def _normalize_terminal_height(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            parsed_height = int(value)
        except (TypeError, ValueError):
            return None
        if parsed_height <= 0:
            return None
        return max(self._MIN_TERMINAL_DOCK_HEIGHT, parsed_height)

    def _current_terminal_height(self) -> int | None:
        if hasattr(self, "terminal_dock") and self.terminal_dock.isVisible():
            return self._normalize_terminal_height(self.terminal_dock.height())
        if hasattr(self, "output_dock") and self.output_dock.isVisible():
            return self._normalize_terminal_height(self.output_dock.height())
        return None

    def _parse_terminal_height_setting(self, payload: object) -> int | None:
        if not isinstance(payload, dict):
            return None

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return None

        terminal_height_value = ui_payload.get("terminal_height")
        if terminal_height_value is None:
            return None

        parsed_terminal_height = self._normalize_terminal_height(terminal_height_value)
        if parsed_terminal_height is None:
            self.log("[settings] Invalid ui.terminal_height; using automatic terminal panel size.")
        return parsed_terminal_height

    def _apply_terminal_height_setting(self, terminal_height: int | None) -> None:
        if terminal_height is None:
            return

        normalized_terminal_height = self._normalize_terminal_height(terminal_height)
        if normalized_terminal_height is None:
            return

        visible_bottom_docks: list[QDockWidget] = []
        if self.output_dock.isVisible():
            visible_bottom_docks.append(self.output_dock)
        if self.terminal_dock.isVisible():
            visible_bottom_docks.append(self.terminal_dock)
        if not visible_bottom_docks:
            return

        self.resizeDocks(
            visible_bottom_docks,
            [normalized_terminal_height] * len(visible_bottom_docks),
            Qt.Orientation.Vertical,
        )

    def _parse_window_size_setting(self, payload: object) -> tuple[int, int] | None:
        if not isinstance(payload, dict):
            return None

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return None

        window_payload = ui_payload.get("window")
        if not isinstance(window_payload, dict):
            return None

        use_last_size = window_payload.get("use_last_size")
        if use_last_size is not True:
            return None

        width_value = window_payload.get("width")
        height_value = window_payload.get("height")
        try:
            width = int(width_value)
            height = int(height_value)
        except (TypeError, ValueError):
            self.log("[settings] Invalid ui.window dimensions; starting maximized.")
            return None

        width = max(self._MIN_WINDOW_WIDTH, width)
        height = max(self._MIN_WINDOW_HEIGHT, height)
        return width, height

    def _apply_bottom_layout_setting(self, layout_mode: str) -> None:
        if layout_mode != self._BOTTOM_LAYOUT_SIDE_BY_SIDE:
            self.log("[layout] Unsupported bottom layout; forcing side by side.")
        self._set_bottom_dock_layout(persist=False)

    def _apply_bottom_panel_visibility_settings(self, output_enabled: bool, terminal_enabled: bool) -> None:
        self._suspend_ui_settings_persistence = True
        try:
            self.output_toggle_action.blockSignals(True)
            self.terminal_toggle_action.blockSignals(True)
            self.output_toggle_action.setChecked(output_enabled)
            self.terminal_toggle_action.setChecked(terminal_enabled)
            self.output_toggle_action.blockSignals(False)
            self.terminal_toggle_action.blockSignals(False)
            self.output_dock.setVisible(output_enabled)
            self.terminal_dock.setVisible(terminal_enabled)
        finally:
            self._suspend_ui_settings_persistence = False

    def _persist_settings_preferences(
        self,
        *,
        autosave_strategy: str | None = None,
        window_use_last_size: bool | None = None,
        window_width: int | None = None,
        window_height: int | None = None,
        python_interpreter: str | None = None,
    ) -> bool:
        settings_path = self._workspace_settings_path()
        payload: dict[str, object] = self._default_settings_payload()

        try:
            self._ensure_workspace_settings_file(settings_path)
            with open(settings_path, "r", encoding="utf-8") as handle:
                parsed_payload = json.load(handle)
            if isinstance(parsed_payload, dict):
                payload = parsed_payload
            else:
                self.log("[settings] Root JSON must be an object; rewriting settings with defaults.")
        except OSError as exc:
            self.log(f"[settings] Could not read {settings_path} for settings persistence: {exc}")
            return False
        except json.JSONDecodeError as exc:
            self.log(f"[settings] Invalid JSON in {settings_path}; rewriting settings sections: {exc}")

        def _normalize_int(value: object, minimum: int, fallback: int) -> int:
            if isinstance(value, bool):
                return fallback
            try:
                parsed_value = int(value)
            except (TypeError, ValueError):
                return fallback
            return max(minimum, parsed_value)

        autosave_payload = payload.get("autosave")
        if not isinstance(autosave_payload, dict):
            autosave_payload = {}
        autosave_payload["enabled"] = self._autosave_enabled
        autosave_payload["interval_seconds"] = self._autosave_interval_seconds
        strategy_value = autosave_strategy if isinstance(autosave_strategy, str) else autosave_payload.get("strategy")
        normalized_strategy = strategy_value.strip() if isinstance(strategy_value, str) else ""
        autosave_payload["strategy"] = normalized_strategy or "backup"
        payload["autosave"] = autosave_payload

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            ui_payload = {}
        ui_payload["theme"] = self._theme_id
        ui_payload["zoom_percent"] = self._ui_zoom_percent
        ui_payload["code_zoom_point_size"] = self._code_zoom_point_size
        ui_payload["bottom_panel_layout"] = self._bottom_layout_mode
        ui_payload["output_enabled"] = self.output_dock.isVisible()
        ui_payload["terminal_enabled"] = self.terminal_dock.isVisible()
        ui_payload["terminal_height"] = (
            self._current_terminal_height() or self._normalize_terminal_height(ui_payload.get("terminal_height"))
        )

        current_width = max(self._MIN_WINDOW_WIDTH, int(self.width()))
        current_height = max(self._MIN_WINDOW_HEIGHT, int(self.height()))
        window_payload = ui_payload.get("window")
        if not isinstance(window_payload, dict):
            window_payload = {}
        existing_use_last_size = window_payload.get("use_last_size")
        resolved_use_last_size = (
            window_use_last_size
            if isinstance(window_use_last_size, bool)
            else (existing_use_last_size if isinstance(existing_use_last_size, bool) else False)
        )
        window_payload["use_last_size"] = resolved_use_last_size
        window_payload["width"] = _normalize_int(
            window_width if window_width is not None else window_payload.get("width"),
            self._MIN_WINDOW_WIDTH,
            current_width,
        )
        window_payload["height"] = _normalize_int(
            window_height if window_height is not None else window_payload.get("height"),
            self._MIN_WINDOW_HEIGHT,
            current_height,
        )
        ui_payload["window"] = window_payload
        payload["ui"] = ui_payload

        python_payload = payload.get("python")
        if not isinstance(python_payload, dict):
            python_payload = {}
        existing_interpreter_value = python_payload.get("interpreter")
        if isinstance(python_interpreter, str):
            resolved_interpreter = python_interpreter.strip()
        elif isinstance(existing_interpreter_value, str):
            resolved_interpreter = existing_interpreter_value.strip()
        else:
            resolved_interpreter = self._normalized_python_interpreter() or ""
        python_payload["interpreter"] = resolved_interpreter
        payload["python"] = python_payload

        try:
            with open(settings_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            self.log(f"[settings] Could not write {settings_path}: {exc}")
            return False

        self._settings_file_path = settings_path
        return True

    def _persist_ui_settings(self) -> None:
        settings_path = self._settings_file_path or self._workspace_settings_path()
        payload: dict[str, object] = self._default_settings_payload()

        try:
            self._ensure_workspace_settings_file(settings_path)
            with open(settings_path, "r", encoding="utf-8") as handle:
                parsed_payload = json.load(handle)
            if isinstance(parsed_payload, dict):
                payload = parsed_payload
            else:
                self.log("[settings] Root JSON must be an object; rewriting with defaults.")
        except OSError as exc:
            self.log(f"[settings] Could not read {settings_path} for UI persistence: {exc}")
            return
        except json.JSONDecodeError as exc:
            self.log(f"[settings] Invalid JSON in {settings_path}; rewriting UI section: {exc}")

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            ui_payload = {}
        ui_payload["theme"] = self._theme_id
        ui_payload["zoom_percent"] = self._ui_zoom_percent
        ui_payload["code_zoom_point_size"] = self._code_zoom_point_size
        ui_payload["bottom_panel_layout"] = self._bottom_layout_mode
        ui_payload["output_enabled"] = self.output_dock.isVisible()
        ui_payload["terminal_enabled"] = self.terminal_dock.isVisible()
        ui_payload["terminal_height"] = (
            self._current_terminal_height() or self._normalize_terminal_height(ui_payload.get("terminal_height"))
        )
        window_payload = ui_payload.get("window")
        if not isinstance(window_payload, dict):
            window_payload = {}
        use_last_size_value = window_payload.get("use_last_size")
        use_last_size = use_last_size_value if isinstance(use_last_size_value, bool) else False
        window_payload["use_last_size"] = use_last_size

        current_width = max(self._MIN_WINDOW_WIDTH, int(self.width()))
        current_height = max(self._MIN_WINDOW_HEIGHT, int(self.height()))

        persisted_width = window_payload.get("width")
        if isinstance(persisted_width, bool):
            persisted_width = current_width
        try:
            normalized_width = int(persisted_width)
        except (TypeError, ValueError):
            normalized_width = current_width
        normalized_width = max(self._MIN_WINDOW_WIDTH, normalized_width)

        persisted_height = window_payload.get("height")
        if isinstance(persisted_height, bool):
            persisted_height = current_height
        try:
            normalized_height = int(persisted_height)
        except (TypeError, ValueError):
            normalized_height = current_height
        normalized_height = max(self._MIN_WINDOW_HEIGHT, normalized_height)

        if use_last_size and not (self.isFullScreen() or self.isMaximized() or self.isMinimized()):
            normalized_width = current_width
            normalized_height = current_height

        window_payload["width"] = normalized_width
        window_payload["height"] = normalized_height
        ui_payload["window"] = window_payload
        payload["ui"] = ui_payload

        try:
            with open(settings_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            self.log(f"[settings] Could not write {settings_path}: {exc}")
            return

        self._settings_file_path = settings_path

    def _load_workspace_settings(self) -> None:
        settings_path = self._workspace_settings_path()
        self._settings_file_path = settings_path
        payload: object = self._default_settings_payload()

        try:
            self._ensure_workspace_settings_file(settings_path)
            with open(settings_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError as exc:
            self.log(f"[settings] Could not access {settings_path}: {exc}")
            self.statusBar().showMessage("Settings file unavailable; autosave defaults applied.", 3500)
        except json.JSONDecodeError as exc:
            self.log(f"[settings] Invalid JSON in {settings_path}: {exc}")
            self.statusBar().showMessage("Settings JSON is invalid; autosave defaults applied.", 3500)

        self._autosave_enabled, self._autosave_interval_seconds = self._parse_autosave_settings(payload)
        self._ui_zoom_percent = self._parse_ui_zoom_setting(payload)
        self._code_zoom_point_size = self._parse_code_zoom_setting(payload)
        self._python_interpreter_path = self._parse_python_interpreter_setting(payload)
        saved_terminal_height = self._parse_terminal_height_setting(payload)
        self._apply_theme(self._parse_theme_setting(payload))
        self._apply_code_zoom_to_open_editors()
        self._update_ui_zoom_actions()
        if not self._startup_window_mode_loaded:
            saved_window_size = self._parse_window_size_setting(payload)
            if saved_window_size is None:
                self._start_maximized = True
            else:
                self._start_maximized = False
                self.resize(*saved_window_size)
            self._startup_window_mode_loaded = True
        self._apply_bottom_layout_setting(self._parse_bottom_layout_setting(payload))
        output_enabled, terminal_enabled = self._parse_bottom_panel_visibility_settings(payload)
        self._apply_bottom_panel_visibility_settings(output_enabled, terminal_enabled)
        QTimer.singleShot(0, lambda height=saved_terminal_height: self._apply_terminal_height_setting(height))
        self._autosave_last_summary = ""
        self._configure_autosave_timer()

    def _workspace_recent_paths_path(self) -> str:
        return os.path.join(self._workspace_settings_dir(), self._RECENT_PATHS_FILE_NAME)

    @staticmethod
    def _default_recent_paths_payload() -> dict[str, object]:
        return {"recent_paths": []}

    def _ensure_recent_paths_file(self, recents_path: str) -> None:
        recents_dir = os.path.dirname(recents_path)
        os.makedirs(recents_dir, exist_ok=True)
        if os.path.exists(recents_path):
            return

        with open(recents_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(self._default_recent_paths_payload(), handle, indent=2)
            handle.write("\n")
        self.log(f"[recents] Created {recents_path}")

    def _load_recent_paths(self) -> None:
        recents_path = self._workspace_recent_paths_path()
        self._recent_paths_file_path = recents_path
        payload: object = self._default_recent_paths_payload()

        try:
            self._ensure_recent_paths_file(recents_path)
            with open(recents_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError as exc:
            self.log(f"[recents] Could not access {recents_path}: {exc}")
            payload = self._default_recent_paths_payload()
        except json.JSONDecodeError as exc:
            self.log(f"[recents] Invalid JSON in {recents_path}: {exc}")
            payload = self._default_recent_paths_payload()

        entries: list[str] = []
        seen_paths: set[str] = set()
        if isinstance(payload, dict):
            raw_entries = payload.get("recent_paths")
            if isinstance(raw_entries, list):
                for value in raw_entries:
                    if not isinstance(value, str):
                        continue
                    candidate = value.strip()
                    if not candidate:
                        continue
                    normalized_candidate = self._normalize_path(candidate)
                    if normalized_candidate in seen_paths:
                        continue
                    seen_paths.add(normalized_candidate)
                    entries.append(os.path.abspath(candidate))
                    if len(entries) >= self._MAX_RECENT_PATHS:
                        break

        self._recent_paths = entries
        self._refresh_welcome_recent_list()

    def _write_recent_paths(self) -> None:
        if not self._recent_paths_file_path:
            return

        payload = {
            "recent_paths": self._recent_paths[: self._MAX_RECENT_PATHS]
        }
        try:
            with open(self._recent_paths_file_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            self.log(f"[recents] Failed to write {self._recent_paths_file_path}: {exc}")

    def _record_recent_path(self, path: str) -> None:
        absolute_path = os.path.abspath(path)
        normalized_new = self._normalize_path(absolute_path)

        updated = [absolute_path]
        for existing in self._recent_paths:
            if self._normalize_path(existing) != normalized_new:
                updated.append(os.path.abspath(existing))

        self._recent_paths = updated[: self._MAX_RECENT_PATHS]
        self._write_recent_paths()
        self._refresh_welcome_recent_list()

    def _autosave_backup_root(self) -> str:
        return os.path.join(self._workspace_settings_dir(), self._AUTOSAVE_DIR_NAME)

    def _autosave_backup_path_for_editor(self, editor: CodeEditor) -> str:
        root = self._autosave_backup_root()
        file_path = self._editor_file_path(editor)

        if file_path:
            absolute_path = os.path.abspath(file_path)
            if self.workspace_root and self._is_same_or_child(absolute_path, self.workspace_root):
                relative = os.path.relpath(absolute_path, self.workspace_root)
                return os.path.join(root, "workspace", relative + ".autosave")

            digest = hashlib.sha1(self._normalize_path(absolute_path).encode("utf-8")).hexdigest()[:12]
            base_name = os.path.basename(absolute_path) or "external"
            return os.path.join(root, "external", f"{base_name}.{digest}.autosave")

        token_value = editor.property("autosave_token")
        if not isinstance(token_value, str) or not token_value:
            token_value = f"editor-{id(editor):x}"
            editor.setProperty("autosave_token", token_value)
        return os.path.join(root, "untitled", f"{token_value}.autosave")

    def _configure_autosave_timer(self) -> None:
        self._autosave_timer.stop()
        if self._autosave_enabled:
            self._autosave_timer.start(self._autosave_interval_seconds * 1000)

        self._update_autosave_status_label()

    def _update_autosave_status_label(self) -> None:
        if self._autosave_enabled:
            text = f"Autosave: {self._autosave_interval_seconds}s (backup)"
        else:
            text = "Autosave: Off"
        if self._autosave_last_summary:
            text = f"{text} | {self._autosave_last_summary}"

        backup_root = self._autosave_backup_root()
        settings_path = self._settings_file_path or self._workspace_settings_path()
        self.autosave_status_label.setText(text)
        self.autosave_status_label.setToolTip(
            f"Settings: {settings_path}\nBackups: {backup_root}"
        )

    def _open_editors(self) -> list[CodeEditor]:
        editors: list[CodeEditor] = []
        seen_ids: set[int] = set()
        for tabs in self._all_tab_widgets():
            for index in range(tabs.count()):
                editor = self._editor_at(tabs, index)
                if editor is None:
                    continue
                editor_id = id(editor)
                if editor_id in seen_ids:
                    continue
                seen_ids.add(editor_id)
                editors.append(editor)
        return editors

    def _run_autosave_cycle(self) -> None:
        if not self._autosave_enabled:
            return

        dirty_editors = [editor for editor in self._open_editors() if editor.document().isModified()]
        timestamp = datetime.now().strftime("%H:%M:%S")
        if not dirty_editors:
            self._autosave_last_summary = f"{timestamp} no changes"
            self._update_autosave_status_label()
            return

        saved_count = 0
        failed_count = 0
        for editor in dirty_editors:
            backup_path = self._autosave_backup_path_for_editor(editor)
            try:
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                with open(backup_path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(editor.toPlainText())
                editor.setProperty("autosave_backup_path", backup_path)
                saved_count += 1
            except OSError as exc:
                failed_count += 1
                self.log(f"[autosave] Failed {self._editor_display_name(editor)} -> {backup_path}: {exc}")

        if failed_count:
            self._autosave_last_summary = f"{timestamp} {saved_count} saved, {failed_count} failed"
            self.statusBar().showMessage("Autosave completed with errors. See Output.", 3500)
        else:
            self._autosave_last_summary = f"{timestamp} {saved_count} backup(s)"

        if saved_count:
            self.log(f"[autosave] Wrote {saved_count} backup(s) to {self._autosave_backup_root()}.")
        self._update_autosave_status_label()

    def _file_signature(self, file_path: str) -> tuple[int, int] | None:
        try:
            stats = os.stat(file_path)
        except OSError:
            return None

        modified_ns = int(getattr(stats, "st_mtime_ns", int(stats.st_mtime * 1_000_000_000)))
        return modified_ns, stats.st_size

    def _record_file_disk_state(self, file_path: str) -> None:
        absolute_path = os.path.abspath(file_path)
        signature = self._file_signature(absolute_path)
        key = self._normalize_path(absolute_path)
        if signature is None:
            self._file_disk_state.pop(key, None)
            return
        self._file_disk_state[key] = signature

    def _mark_internal_write(self, file_path: str) -> None:
        self._recent_internal_writes[self._normalize_path(file_path)] = time.monotonic()

    def _prune_recent_internal_writes(self) -> None:
        now = time.monotonic()
        stale_keys = [
            key for key, timestamp in self._recent_internal_writes.items()
            if now - timestamp > self._FILE_WATCH_INTERNAL_WRITE_GRACE_SECONDS * 4
        ]
        for key in stale_keys:
            self._recent_internal_writes.pop(key, None)

    def _is_recent_internal_write(self, file_path: str) -> bool:
        self._prune_recent_internal_writes()
        timestamp = self._recent_internal_writes.get(self._normalize_path(file_path))
        if timestamp is None:
            return False
        return (time.monotonic() - timestamp) <= self._FILE_WATCH_INTERNAL_WRITE_GRACE_SECONDS

    def _refresh_workspace_tree_after_external_change(self) -> None:
        if not self.workspace_root:
            return
        root_index = self.fs_model.index(self.workspace_root)
        if root_index.isValid():
            self.file_tree.setRootIndex(root_index)
        self.file_tree.viewport().update()

    def _sync_file_watcher_paths(self) -> None:
        desired_directories: dict[str, str] = {}
        if self.workspace_root:
            workspace_path = os.path.abspath(self.workspace_root)
            if os.path.isdir(workspace_path):
                desired_directories[self._normalize_path(workspace_path)] = workspace_path

        current_directories = {
            self._normalize_path(path): path
            for path in self._file_watcher.directories()
        }
        directory_removals = [
            path for key, path in current_directories.items()
            if key not in desired_directories
        ]
        directory_additions = [
            path for key, path in desired_directories.items()
            if key not in current_directories
        ]

        desired_files: dict[str, str] = {}
        for tabs in self._all_tab_widgets():
            for index in range(tabs.count()):
                widget = self._tab_widget_at(tabs, index)
                if widget is None:
                    continue
                file_path = self._widget_file_path(widget)
                if not file_path:
                    continue
                absolute_path = os.path.abspath(file_path)
                if os.path.isfile(absolute_path):
                    desired_files[self._normalize_path(absolute_path)] = absolute_path

        current_files = {
            self._normalize_path(path): path
            for path in self._file_watcher.files()
        }
        file_removals = [
            path for key, path in current_files.items()
            if key not in desired_files
        ]
        file_additions = [
            path for key, path in desired_files.items()
            if key not in current_files
        ]

        if directory_removals:
            self._file_watcher.removePaths(directory_removals)
        if file_removals:
            self._file_watcher.removePaths(file_removals)

        if directory_additions:
            not_added_directories = self._file_watcher.addPaths(directory_additions)
            for path in not_added_directories:
                self.log(f"[watcher] Could not watch directory: {path}")

        if file_additions:
            not_added_files = self._file_watcher.addPaths(file_additions)
            for path in not_added_files:
                self.log(f"[watcher] Could not watch file: {path}")

        for path in desired_files.values():
            self._record_file_disk_state(path)

    def _on_watched_directory_changed(self, changed_path: str) -> None:
        absolute_changed = os.path.abspath(changed_path)
        if self.workspace_root and self._paths_equal(absolute_changed, self.workspace_root):
            self._refresh_workspace_tree_after_external_change()
        self._sync_file_watcher_paths()

    def _on_watched_file_changed(self, changed_path: str) -> None:
        self._handle_external_file_change(changed_path, source="watcher")
        self._sync_file_watcher_paths()

    def _poll_watched_files(self) -> None:
        if not self._open_editors_by_path and not self._open_image_tabs_by_path:
            self._prune_recent_internal_writes()
            return

        for tabs in self._all_tab_widgets():
            for index in range(tabs.count()):
                widget = self._tab_widget_at(tabs, index)
                if widget is None:
                    continue
                file_path = self._widget_file_path(widget)
                if not file_path:
                    continue
                self._handle_external_file_change(file_path, source="poll")

    def _handle_external_file_change(self, file_path: str, source: str) -> None:
        absolute_path = os.path.abspath(file_path)
        key = self._normalize_path(absolute_path)
        widget: QWidget | None = self._open_editors_by_path.get(key)
        if widget is None:
            widget = self._open_image_tabs_by_path.get(key)
        if widget is None:
            return

        if self._is_recent_internal_write(absolute_path):
            self._record_file_disk_state(absolute_path)
            return

        current_signature = self._file_signature(absolute_path)
        previous_signature = self._file_disk_state.get(key)
        if source == "poll" and current_signature == previous_signature:
            return
        if source == "watcher" and previous_signature is not None and current_signature == previous_signature:
            return

        if current_signature is None:
            self._file_disk_state.pop(key, None)
            self.statusBar().showMessage(f"File missing on disk: {absolute_path}", 2500)
            self.log(f"[watcher] File missing on disk: {absolute_path}")
            return

        if isinstance(widget, ImageViewer):
            self._reload_image_viewer_from_disk(widget, reason="external change")
            return

        if key in self._external_change_prompts:
            return

        editor = widget if isinstance(widget, CodeEditor) else None
        if editor is None:
            return

        if editor.document().isModified():
            self._external_change_prompts.add(key)
            try:
                answer = QMessageBox.question(
                    self,
                    "External File Change",
                    (
                        f"This file changed on disk:\n{absolute_path}\n\n"
                        "You have unsaved changes in Temcode.\n"
                        "Reload from disk and discard editor changes?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
            finally:
                self._external_change_prompts.discard(key)

            if answer == QMessageBox.StandardButton.Yes:
                self._reload_editor_from_disk(editor, reason="external change")
            else:
                self._file_disk_state[key] = current_signature
                self.statusBar().showMessage("Kept local unsaved changes.", 1800)
                self.log(f"[watcher] Kept unsaved editor content for {absolute_path}.")
            return

        self._reload_editor_from_disk(editor, reason="external change")

    def _reload_image_viewer_from_disk(self, viewer: ImageViewer, reason: str) -> bool:
        file_path = self._widget_file_path(viewer)
        if not file_path:
            return False

        absolute_path = os.path.abspath(file_path)
        if not viewer.reload_image():
            self.statusBar().showMessage(f"Could not reload image: {absolute_path}", 2500)
            self.log(f"[watcher] Failed to reload image: {absolute_path}")
            return False

        if viewer is self._current_tab_widget():
            self._update_editor_mode_status(viewer)
            self._refresh_breadcrumbs(viewer)

        self._record_file_disk_state(absolute_path)
        self.statusBar().showMessage(f"Reloaded {absolute_path} ({reason}).", 2500)
        self.log(f"[watcher] Reloaded image from disk: {absolute_path} ({reason}).")
        self._refresh_git_after_path_change()
        return True

    def _reload_editor_from_disk(self, editor: CodeEditor, reason: str) -> bool:
        file_path = self._editor_file_path(editor)
        if not file_path:
            return False

        absolute_path = os.path.abspath(file_path)
        try:
            content = self._read_text_file(absolute_path)
        except OSError as exc:
            self._show_error("Reload File", absolute_path, exc)
            return False

        cursor_position = editor.textCursor().position()
        scroll_value = editor.verticalScrollBar().value()

        editor.setPlainText(content)
        editor.document().setModified(False)

        large_file_mode, large_file_reason = self._evaluate_large_file_mode(absolute_path, content)
        editor.setProperty("large_file_mode", large_file_mode)
        editor.setProperty("large_file_mode_reason", large_file_reason)
        editor.configure_syntax_highlighting(absolute_path, large_file_mode)
        self._schedule_lsp_document_sync(editor, immediate=True)

        max_position = max(0, editor.document().characterCount() - 1)
        cursor = editor.textCursor()
        cursor.setPosition(min(cursor_position, max_position))
        editor.setTextCursor(cursor)
        editor.verticalScrollBar().setValue(min(scroll_value, editor.verticalScrollBar().maximum()))

        self._update_editor_tab_title(editor)
        if editor is self._current_editor():
            self._update_editor_mode_status(editor)
            self._refresh_breadcrumbs(editor)
            self._apply_lsp_diagnostics_to_editor(editor)
            if self.find_panel.isVisible():
                self._refresh_find_highlights()

        self._record_file_disk_state(absolute_path)
        self.statusBar().showMessage(f"Reloaded {absolute_path} ({reason}).", 2500)
        self.log(f"[watcher] Reloaded file from disk: {absolute_path} ({reason}).")
        self._refresh_git_after_path_change()
        return True

    def _request_close_tab(self, tabs: QTabWidget, tab_index: int) -> None:
        widget = self._tab_widget_at(tabs, tab_index)
        if widget is None:
            return

        self._set_active_tab_widget(tabs)
        if not self._confirm_close_editor(widget):
            return

        self._close_editor_tab(tabs, tab_index)

    def _close_editor_tab(self, tabs: QTabWidget, tab_index: int) -> None:
        widget = self._tab_widget_at(tabs, tab_index)
        if widget is None:
            return

        editor = widget if isinstance(widget, CodeEditor) else None
        if editor is not None:
            self._close_lsp_document(editor)

        file_path = self._widget_file_path(widget)
        if file_path:
            key = self._normalize_path(file_path)
            self._open_editors_by_path.pop(key, None)
            self._open_image_tabs_by_path.pop(key, None)
            self._file_disk_state.pop(key, None)
            self._recent_internal_writes.pop(key, None)

        if editor is not None and self._find_highlight_editor is editor:
            self._find_highlight_editor = None

        tabs.removeTab(tab_index)
        widget.deleteLater()
        self._sync_file_watcher_paths()
        self._update_editor_surface()
        self._refresh_welcome_recent_list()

        if tabs.count() == 0 and self._active_editor_tabs is tabs:
            self._active_editor_tabs = self.primary_tabs if tabs is self.secondary_tabs else tabs

    def _confirm_close_editor(self, widget: QWidget) -> bool:
        editor = widget if isinstance(widget, CodeEditor) else None
        if editor is None:
            return True

        if not editor.document().isModified():
            return True

        display_name = self._editor_display_name(editor)
        answer = QMessageBox.warning(
            self,
            "Unsaved Changes",
            f"Save changes to {display_name}?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Save:
            return self._save_editor(editor, save_as=False)
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _set_split_enabled(self, enabled: bool) -> None:
        if enabled:
            self.secondary_tabs.show()
            if self.secondary_tabs.count() == 0:
                self.editor_splitter.setSizes([1, 1])
            self.log("[editor] Split view enabled")
            self._update_editor_surface()
            return

        while self.secondary_tabs.count() > 0:
            widget = self._tab_widget_at(self.secondary_tabs, 0)
            if widget is None:
                self.secondary_tabs.removeTab(0)
                continue

            title = self.secondary_tabs.tabText(0)
            tooltip = self.secondary_tabs.tabToolTip(0)
            self.secondary_tabs.removeTab(0)

            new_index = self._add_editor_tab(self.primary_tabs, widget, title)
            self.primary_tabs.setTabToolTip(new_index, tooltip)

        self.secondary_tabs.hide()
        self._set_active_tab_widget(self.primary_tabs)
        self.log("[editor] Split view disabled")
        self._update_editor_surface()

    def move_current_tab_to_other_split(self) -> None:
        current_tabs = self._active_editor_tabs or self.primary_tabs
        widget = self._current_tab_widget(current_tabs)
        if widget is None:
            return

        if not self.secondary_tabs.isVisible():
            self.split_toggle_action.setChecked(True)

        target_tabs = self.secondary_tabs if current_tabs is self.primary_tabs else self.primary_tabs
        tab_index = current_tabs.indexOf(widget)
        if tab_index < 0:
            return

        title = current_tabs.tabText(tab_index)
        tooltip = current_tabs.tabToolTip(tab_index)
        current_tabs.removeTab(tab_index)

        new_index = self._add_editor_tab(target_tabs, widget, title)
        target_tabs.setTabToolTip(new_index, tooltip)
        target_tabs.setCurrentIndex(new_index)
        self._set_active_tab_widget(target_tabs)
        widget.setFocus()
        self._refresh_breadcrumbs(widget)
        self.log(f"[editor] Moved tab to {'secondary' if target_tabs is self.secondary_tabs else 'primary'} split")

    def _on_current_tab_changed(self, tabs: QTabWidget, tab_index: int) -> None:
        if tab_index < 0:
            self._update_editor_surface()
            self._update_editor_mode_status(None)
            self._refresh_breadcrumbs(None)
            if self.find_panel.isVisible():
                self._refresh_find_highlights()
            return

        self._set_active_tab_widget(tabs)
        widget = self._tab_widget_at(tabs, tab_index)
        if widget is None:
            self._update_editor_surface()
            self._update_editor_mode_status(None)
            self._refresh_breadcrumbs(None)
            if self.find_panel.isVisible():
                self._refresh_find_highlights()
            return

        file_path = self._widget_file_path(widget)
        if file_path:
            self._reveal_path(file_path)
        self._update_editor_mode_status(widget)
        self._refresh_breadcrumbs(widget)

        editor = widget if isinstance(widget, CodeEditor) else None
        if editor is not None:
            self._apply_lsp_diagnostics_to_editor(editor)

        self._update_editor_surface()
        if self.find_panel.isVisible():
            self._refresh_find_highlights()

    def _set_active_tab_widget(self, tabs: QTabWidget) -> None:
        self._active_editor_tabs = tabs
        self._refresh_breadcrumbs(self._current_tab_widget(tabs))
        self._refresh_lsp_status_label()

    def _reveal_path(self, file_path: str) -> None:
        index = self.fs_model.index(file_path)
        if not index.isValid():
            return

        parent = index.parent()
        while parent.isValid():
            self.file_tree.expand(parent)
            parent = parent.parent()

        self.file_tree.setCurrentIndex(index)
        self.file_tree.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _update_editor_tab_title(self, widget: QWidget) -> None:
        tabs = self._find_tab_widget_for_editor(widget)
        if tabs is None:
            return

        tab_index = tabs.indexOf(widget)
        if tab_index < 0:
            return

        display_name = self._widget_display_name(widget)
        dirty_prefix = "*" if isinstance(widget, CodeEditor) and widget.document().isModified() else ""
        tabs.setTabText(tab_index, f"{dirty_prefix}{display_name}")

        file_path = self._widget_file_path(widget)
        tabs.setTabToolTip(tab_index, file_path or display_name)

    def _update_open_tabs_after_rename(self, old_path: str, new_path: str) -> None:
        old_key = self._normalize_path(old_path)
        direct_widget: QWidget | None = self._open_editors_by_path.pop(old_key, None)
        if direct_widget is None:
            direct_widget = self._open_image_tabs_by_path.pop(old_key, None)
        if direct_widget is not None:
            self._apply_new_editor_path(direct_widget, new_path)
            return

        moved_widgets: list[tuple[QWidget, str]] = []
        open_widgets: list[QWidget] = list(self._open_editors_by_path.values()) + list(self._open_image_tabs_by_path.values())
        for widget in open_widgets:
            file_path_value = self._widget_file_path(widget)
            if file_path_value and self._is_same_or_child(file_path_value, old_path):
                relative = os.path.relpath(file_path_value, old_path)
                moved_widgets.append((widget, os.path.join(new_path, relative)))

        for widget, updated_path in moved_widgets:
            old_widget_path = self._widget_file_path(widget)
            if old_widget_path:
                old_key_for_widget = self._normalize_path(old_widget_path)
                self._open_editors_by_path.pop(old_key_for_widget, None)
                self._open_image_tabs_by_path.pop(old_key_for_widget, None)
            self._apply_new_editor_path(widget, updated_path)

    def _apply_new_editor_path(self, widget: QWidget, new_path: str) -> None:
        old_path = self._widget_file_path(widget)
        absolute_path = os.path.abspath(new_path)

        editor = widget if isinstance(widget, CodeEditor) else None
        viewer = widget if isinstance(widget, ImageViewer) else None

        if editor is not None and old_path and not self._paths_equal(old_path, absolute_path):
            self._lsp_client.close_document(old_path)
            self._clear_lsp_diagnostics_for_path(old_path)

        if editor is not None:
            editor.setProperty("file_path", absolute_path)
            large_file_mode = bool(editor.property("large_file_mode"))
            editor.configure_syntax_highlighting(absolute_path, large_file_mode)

        if viewer is not None:
            viewer.setProperty("file_path", absolute_path)
            viewer.set_image_path(absolute_path)

        if old_path:
            old_key = self._normalize_path(old_path)
            self._file_disk_state.pop(old_key, None)
            self._recent_internal_writes.pop(old_key, None)

        new_key = self._normalize_path(absolute_path)
        if editor is not None:
            self._open_editors_by_path[new_key] = editor
        if viewer is not None:
            self._open_image_tabs_by_path[new_key] = viewer

        self._record_file_disk_state(absolute_path)
        self._sync_file_watcher_paths()
        self._update_editor_tab_title(widget)

        if editor is not None:
            self._schedule_lsp_document_sync(editor, immediate=True)
            self._apply_lsp_diagnostics_to_editor(editor)

        if widget is self._current_tab_widget():
            self._update_editor_mode_status(widget)
            self._refresh_breadcrumbs(widget)
        self._refresh_git_after_path_change(rescan_repositories=True)

    def _close_tabs_for_deleted_path(self, deleted_path: str) -> None:
        for tabs in self._all_tab_widgets():
            for index in reversed(range(tabs.count())):
                widget = self._tab_widget_at(tabs, index)
                if widget is None:
                    continue
                file_path = self._widget_file_path(widget)
                if file_path and self._is_same_or_child(file_path, deleted_path):
                    self._close_editor_tab(tabs, index)

    def _find_tab_widget_for_editor(self, widget: QWidget) -> QTabWidget | None:
        for tabs in self._all_tab_widgets():
            if tabs.indexOf(widget) >= 0:
                return tabs
        return None

    def _all_tab_widgets(self) -> tuple[QTabWidget, QTabWidget]:
        return self.primary_tabs, self.secondary_tabs

    def _tab_widget_at(self, tabs: QTabWidget, tab_index: int) -> QWidget | None:
        widget = tabs.widget(tab_index)
        if isinstance(widget, QWidget):
            return widget
        return None

    def _editor_at(self, tabs: QTabWidget, tab_index: int) -> CodeEditor | None:
        widget = self._tab_widget_at(tabs, tab_index)
        if isinstance(widget, CodeEditor):
            return widget
        return None

    def _current_tab_widget(self, tabs: QTabWidget | None = None) -> QWidget | None:
        active_tabs = tabs or self._active_editor_tabs or self.primary_tabs
        widget = self._tab_widget_at(active_tabs, active_tabs.currentIndex())
        if widget is not None:
            return widget

        for tab_widget in self._all_tab_widgets():
            if tab_widget is active_tabs:
                continue
            fallback_widget = self._tab_widget_at(tab_widget, tab_widget.currentIndex())
            if fallback_widget is not None:
                return fallback_widget
        return None

    def _current_editor(self, tabs: QTabWidget | None = None) -> CodeEditor | None:
        widget = self._current_tab_widget(tabs)
        if isinstance(widget, CodeEditor):
            return widget
        return None

    def _widget_file_path(self, widget: QWidget) -> str | None:
        value = widget.property("file_path")
        if isinstance(value, str) and value:
            return value
        return None

    def _widget_display_name(self, widget: QWidget) -> str:
        file_path = self._widget_file_path(widget)
        if file_path:
            return os.path.basename(file_path)

        display_name = widget.property("display_name")
        if isinstance(display_name, str) and display_name:
            return display_name
        return "Untitled"

    def _editor_file_path(self, editor: CodeEditor) -> str | None:
        return self._widget_file_path(editor)

    def _editor_display_name(self, editor: CodeEditor) -> str:
        return self._widget_display_name(editor)

    def _close_all_open_editors(self) -> bool:
        for tabs in self._all_tab_widgets():
            for index in reversed(range(tabs.count())):
                widget = self._tab_widget_at(tabs, index)
                if widget is None:
                    continue
                if not self._confirm_close_editor(widget):
                    return False
                self._close_editor_tab(tabs, index)
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API)
        self._is_app_closing = True
        self._autosave_timer.stop()
        self._ui_settings_persist_timer.stop()
        self._file_poll_timer.stop()
        if self.terminal_console is not None and not self.terminal_console.shutdown(timeout_ms=2500):
            QMessageBox.warning(
                self,
                "Terminal Busy",
                "The terminal session is still stopping. Please try closing again.",
            )
            self._is_app_closing = False
            event.ignore()
            return
        if not self._close_all_open_editors():
            self._is_app_closing = False
            event.ignore()
            return

        self._persist_ui_settings()
        self._lsp_client.stop()
        event.accept()

    @staticmethod
    def _read_text_file(file_path: str) -> str:
        with open(file_path, "rb") as handle:
            raw = handle.read()

        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _normalize_path(path: str) -> str:
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def _paths_equal(self, left: str, right: str | None) -> bool:
        if right is None:
            return False
        return self._normalize_path(left) == self._normalize_path(right)

    def _is_same_or_child(self, candidate_path: str, parent_path: str) -> bool:
        candidate = self._normalize_path(candidate_path)
        parent = self._normalize_path(parent_path).rstrip("\\/")
        return candidate == parent or candidate.startswith(parent + os.sep)

    def _show_error(self, action_name: str, path: str, error: OSError) -> None:
        message = f"{action_name} failed:\n{path}\n\n{error}"
        QMessageBox.critical(self, action_name, message)
        self.log(f"[error] {message}")

    def log(self, message: str) -> None:
        if hasattr(self, "output_panel"):
            self.output_panel.appendPlainText(message)
