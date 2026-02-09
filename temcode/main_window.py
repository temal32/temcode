from __future__ import annotations

import json
import os
import shutil
import hashlib
import time
from datetime import datetime

from PySide6.QtCore import QDir, QFileSystemWatcher, QModelIndex, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QFileDialog,
    QFileSystemModel,
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
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from temcode.editor import CodeEditor
from temcode.terminal import CmdTerminalWidget


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
    _BOTTOM_LAYOUT_STACKED = "stacked"
    _BOTTOM_LAYOUT_SIDE_BY_SIDE = "side_by_side"
    _MIN_WINDOW_WIDTH = 640
    _MIN_WINDOW_HEIGHT = 420

    def __init__(self) -> None:
        super().__init__()
        self.workspace_root: str | None = None
        self._open_editors_by_path: dict[str, CodeEditor] = {}
        self._untitled_counter = 1
        self._active_editor_tabs: QTabWidget | None = None
        self._find_highlight_editor: CodeEditor | None = None
        self._autosave_enabled = self._DEFAULT_AUTOSAVE_ENABLED
        self._autosave_interval_seconds = self._DEFAULT_AUTOSAVE_INTERVAL_SECONDS
        self._autosave_last_summary = ""
        self._settings_file_path: str | None = None
        self._recent_paths_file_path: str | None = None
        self._recent_paths: list[str] = []
        self._bottom_layout_mode = self._BOTTOM_LAYOUT_STACKED
        self._suspend_ui_settings_persistence = False
        self._is_app_closing = False
        self._start_maximized = True
        self._startup_window_mode_loaded = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(False)
        self._autosave_timer.timeout.connect(self._run_autosave_cycle)
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

        self.setWindowTitle("Temcode")
        self.resize(1920, 980)

        self._build_menu_bar()
        self._build_status_bar()
        self._build_central_editor_area()
        self._build_solution_explorer_dock()
        self._build_output_dock()
        self._build_terminal_dock()

        self._load_workspace_settings()
        self._load_recent_paths()
        self._sync_file_watcher_paths()
        self._refresh_breadcrumbs()
        self._update_solution_explorer_surface()
        self._file_poll_timer.start()

    def should_start_maximized(self) -> bool:
        return self._start_maximized

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        view_menu = self.menuBar().addMenu("&View")
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

        self.solution_explorer_toggle_action = QAction("Solution Explorer", self)
        self.output_toggle_action = QAction("Output", self)
        self.terminal_toggle_action = QAction("Terminal", self)
        self.split_toggle_action = QAction("Split Editor", self)
        self.split_toggle_action.setCheckable(True)
        self.split_toggle_action.toggled.connect(self._set_split_enabled)
        self.bottom_layout_action_group = QActionGroup(self)
        self.bottom_layout_action_group.setExclusive(True)

        self.bottom_layout_stacked_action = QAction("Stacked", self)
        self.bottom_layout_stacked_action.setCheckable(True)

        self.bottom_layout_side_by_side_action = QAction("Side by Side", self)
        self.bottom_layout_side_by_side_action.setCheckable(True)

        self.bottom_layout_action_group.addAction(self.bottom_layout_stacked_action)
        self.bottom_layout_action_group.addAction(self.bottom_layout_side_by_side_action)
        self.bottom_layout_stacked_action.setChecked(True)
        self.bottom_layout_stacked_action.toggled.connect(
            lambda checked: checked and self._set_bottom_dock_layout(self._BOTTOM_LAYOUT_STACKED)
        )
        self.bottom_layout_side_by_side_action.toggled.connect(
            lambda checked: checked and self._set_bottom_dock_layout(self._BOTTOM_LAYOUT_SIDE_BY_SIDE)
        )

        self.move_tab_to_other_split_action = QAction("Move Tab To Other Split", self)
        self.move_tab_to_other_split_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.move_tab_to_other_split_action.triggered.connect(self.move_current_tab_to_other_split)

        view_menu.addAction(self.solution_explorer_toggle_action)
        view_menu.addAction(self.output_toggle_action)
        view_menu.addAction(self.terminal_toggle_action)
        view_menu.addSeparator()
        bottom_layout_menu = view_menu.addMenu("Bottom Panel Layout")
        bottom_layout_menu.addAction(self.bottom_layout_stacked_action)
        bottom_layout_menu.addAction(self.bottom_layout_side_by_side_action)
        view_menu.addSeparator()
        view_menu.addAction(self.split_toggle_action)
        view_menu.addAction(self.move_tab_to_other_split_action)

        about_action = QAction("&About Temcode", self)
        about_action.triggered.connect(lambda: self.statusBar().showMessage("Temcode v0.2", 2500))
        help_menu.addAction(about_action)

    def _build_status_bar(self) -> None:
        self.statusBar().showMessage("Ready")
        self.autosave_status_label = QLabel("Autosave: configuring")
        self.autosave_status_label.setObjectName("autosaveStatusLabel")
        self.language_status_label = QLabel("Plain Text")
        self.language_status_label.setObjectName("languageStatusLabel")
        self.large_file_status_label = QLabel("")
        self.large_file_status_label.setObjectName("largeFileStatusLabel")
        self.large_file_status_label.setStyleSheet("color: #f0c674; font-weight: 600;")
        self.statusBar().addPermanentWidget(self.autosave_status_label)
        self.statusBar().addPermanentWidget(self.language_status_label)
        self.statusBar().addPermanentWidget(self.large_file_status_label)

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

        title_label = QLabel("Welcome to Temcode", panel)
        title_label.setObjectName("welcomeTitle")

        subtitle_label = QLabel(
            "Open a file or folder, or continue from a recent path.",
            panel,
        )
        subtitle_label.setObjectName("welcomeSubtitle")

        action_row = QWidget(panel)
        action_row_layout = QHBoxLayout(action_row)
        action_row_layout.setContentsMargins(0, 0, 0, 0)
        action_row_layout.setSpacing(8)

        open_file_button = QPushButton("Open File...", action_row)
        open_file_button.setObjectName("welcomeActionButton")
        open_file_button.clicked.connect(self.open_file_dialog)

        open_folder_button = QPushButton("Open Folder...", action_row)
        open_folder_button.setObjectName("welcomeActionButton")
        open_folder_button.clicked.connect(self.open_folder_dialog)

        open_recent_button = QPushButton("Open Selected Recent", action_row)
        open_recent_button.setObjectName("welcomeActionButton")
        open_recent_button.clicked.connect(self._open_selected_recent_path)

        action_row_layout.addWidget(open_file_button, 0)
        action_row_layout.addWidget(open_folder_button, 0)
        action_row_layout.addWidget(open_recent_button, 0)
        action_row_layout.addStretch(1)

        recent_label = QLabel("Recent Files and Paths", panel)
        recent_label.setObjectName("welcomeRecentLabel")

        self.welcome_recent_list = QListWidget(panel)
        self.welcome_recent_list.setObjectName("welcomeRecentList")
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

    def _refresh_breadcrumbs(self, editor: CodeEditor | None = None) -> None:
        target_editor = editor if editor is not None else self._current_editor()
        self._render_breadcrumbs(self._breadcrumb_segments_for_editor(target_editor))

    def _breadcrumb_segments_for_editor(self, editor: CodeEditor | None) -> list[str]:
        if editor is None:
            return ["Workspace"]

        file_path = self._editor_file_path(editor)
        if not file_path:
            return ["Workspace", self._editor_display_name(editor)]

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

    def _render_breadcrumbs(self, segments: list[str]) -> None:
        while self.breadcrumbs_layout.count():
            item = self.breadcrumbs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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

    def _create_editor_tabs(self, object_name: str) -> QTabWidget:
        tabs = QTabWidget(self)
        tabs.setObjectName(object_name)
        tabs.setDocumentMode(True)
        tabs.setMovable(True)
        tabs.setTabsClosable(True)
        tabs.tabCloseRequested.connect(lambda i, t=tabs: self._request_close_tab(t, i))
        tabs.currentChanged.connect(lambda i, t=tabs: self._on_current_tab_changed(t, i))
        tabs.tabBarClicked.connect(lambda _i, t=tabs: self._set_active_tab_widget(t))
        tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabs.tabBar().customContextMenuRequested.connect(
            lambda pos, t=tabs: self._show_tab_context_menu(t, pos)
        )
        return tabs

    def _build_solution_explorer_dock(self) -> None:
        self.solution_explorer_dock = QDockWidget("Solution Explorer", self)
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

        self.solution_explorer_dock.setWidget(self.solution_explorer_stack)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.solution_explorer_dock)
        self.solution_explorer_toggle_action.setCheckable(True)
        self.solution_explorer_toggle_action.setChecked(True)
        self.solution_explorer_toggle_action.toggled.connect(self.solution_explorer_dock.setVisible)
        self.solution_explorer_dock.visibilityChanged.connect(self.solution_explorer_toggle_action.setChecked)
        self._update_solution_explorer_surface()

    def _update_solution_explorer_surface(self) -> None:
        if not hasattr(self, "solution_explorer_stack"):
            return

        if self.workspace_root and os.path.isdir(self.workspace_root):
            self.solution_explorer_stack.setCurrentWidget(self.file_tree)
        else:
            self.solution_explorer_stack.setCurrentWidget(self.solution_explorer_placeholder)

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

        self.output_dock.setWidget(self.output_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)
        self.output_toggle_action.setCheckable(True)
        self.output_toggle_action.setChecked(True)
        self.output_toggle_action.toggled.connect(self.output_dock.setVisible)
        self.output_dock.visibilityChanged.connect(self._on_output_dock_visibility_changed)

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
        self._set_bottom_dock_layout(self._bottom_layout_mode, persist=False)

        self.terminal_toggle_action.setCheckable(True)
        self.terminal_toggle_action.setChecked(True)
        self.terminal_toggle_action.toggled.connect(self.terminal_dock.setVisible)
        self.terminal_dock.visibilityChanged.connect(self._on_terminal_dock_visibility_changed)

    def _set_bottom_dock_layout(self, layout_mode: str, persist: bool = True) -> None:
        if layout_mode not in {self._BOTTOM_LAYOUT_STACKED, self._BOTTOM_LAYOUT_SIDE_BY_SIDE}:
            return

        self._bottom_layout_mode = layout_mode
        if not hasattr(self, "output_dock") or not hasattr(self, "terminal_dock"):
            return

        if layout_mode == self._BOTTOM_LAYOUT_SIDE_BY_SIDE:
            orientation = Qt.Orientation.Horizontal
            layout_label = "side by side"
        else:
            orientation = Qt.Orientation.Vertical
            layout_label = "stacked"

        self.splitDockWidget(self.output_dock, self.terminal_dock, orientation)
        self.resizeDocks([self.output_dock, self.terminal_dock], [1, 1], orientation)
        if persist:
            self._persist_ui_settings()
        self.log(f"[layout] Bottom panels set to {layout_label}.")

    def _on_output_dock_visibility_changed(self, is_visible: bool) -> None:
        self.output_toggle_action.blockSignals(True)
        self.output_toggle_action.setChecked(is_visible)
        self.output_toggle_action.blockSignals(False)
        if not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def _on_terminal_dock_visibility_changed(self, is_visible: bool) -> None:
        self.terminal_toggle_action.blockSignals(True)
        self.terminal_toggle_action.setChecked(is_visible)
        self.terminal_toggle_action.blockSignals(False)
        if not self._suspend_ui_settings_persistence and not self._is_app_closing:
            self._persist_ui_settings()

    def open_file_dialog(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", start_dir, "All Files (*.*)")
        if file_path:
            self.open_file(file_path)

    def open_folder_dialog(self) -> None:
        start_dir = self.workspace_root or os.getcwd()
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", start_dir)
        if folder:
            self.set_workspace_root(folder)

    def close_workspace(self) -> None:
        if not self._close_all_open_editors():
            return

        closed_workspace = self.workspace_root
        self.workspace_root = None
        self._settings_file_path = None

        root_index = self.fs_model.setRootPath("")
        self.file_tree.setRootIndex(root_index)
        self.solution_explorer_dock.setWindowTitle("Solution Explorer")
        self.setWindowTitle("Temcode")

        if self.terminal_console is not None:
            self.terminal_console.set_working_directory(os.getcwd())

        self._sync_file_watcher_paths()
        self._update_editor_mode_status(None)
        self._refresh_breadcrumbs(None)
        self._update_solution_explorer_surface()
        self._update_editor_surface()

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
        workspace_name = os.path.basename(normalized.rstrip("\\/")) or normalized
        self.solution_explorer_dock.setWindowTitle(f"Solution Explorer - {workspace_name}")
        self.setWindowTitle(f"Temcode - {normalized}")
        self.statusBar().showMessage(f"Workspace: {normalized}", 3000)
        self.log(f"[workspace] Opened folder: {normalized}")
        self._load_workspace_settings()
        self._load_recent_paths()
        if track_recent:
            self._record_recent_path(normalized)
        if self.terminal_console is not None:
            self.terminal_console.set_working_directory(normalized)
        self._sync_file_watcher_paths()
        self._refresh_breadcrumbs()
        self._update_solution_explorer_surface()
        self._update_editor_surface()

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

        menu = QMenu(self)
        move_action = menu.addAction("Move To Other Split")
        close_action = menu.addAction("Close")

        selected = menu.exec(tabs.tabBar().mapToGlobal(pos))
        if selected == move_action:
            tabs.setCurrentIndex(tab_index)
            self._set_active_tab_widget(tabs)
            self.move_current_tab_to_other_split()
        elif selected == close_action:
            self._request_close_tab(tabs, tab_index)

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
        tab_index = target_tabs.addTab(editor, display_name)
        target_tabs.setTabToolTip(tab_index, display_name)
        target_tabs.setCurrentIndex(tab_index)
        self._set_active_tab_widget(target_tabs)
        self._update_editor_surface()
        editor.setFocus()
        self._update_editor_mode_status(editor)
        self._refresh_breadcrumbs(editor)
        self.log(f"[editor] New file: {display_name}")

    def _create_new_file(self, parent_dir: str) -> None:
        file_name, ok = QInputDialog.getText(self, "New File", "File name:")
        if not ok:
            return

        file_name = file_name.strip()
        if not file_name:
            return

        full_path = os.path.join(parent_dir, file_name)
        if os.path.exists(full_path):
            QMessageBox.warning(self, "Create File", f"A file or folder already exists:\n{full_path}")
            return

        try:
            with open(full_path, "x", encoding="utf-8"):
                pass
            self.log(f"[file] Created file: {full_path}")
            self._reveal_path(full_path)
        except OSError as exc:
            self._show_error("Create File", full_path, exc)

    def _create_new_folder(self, parent_dir: str) -> None:
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok:
            return

        folder_name = folder_name.strip()
        if not folder_name:
            return

        full_path = os.path.join(parent_dir, folder_name)
        if os.path.exists(full_path):
            QMessageBox.warning(self, "Create Folder", f"A file or folder already exists:\n{full_path}")
            return

        try:
            os.mkdir(full_path)
            self.log(f"[file] Created folder: {full_path}")
            self._reveal_path(full_path)
        except OSError as exc:
            self._show_error("Create Folder", full_path, exc)

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
                self._record_file_disk_state(absolute_path)
                self._record_recent_path(absolute_path)
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
        tab_index = target_tabs.addTab(editor, "")
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
            return False
        return self._save_editor(editor, save_as=False)

    def save_current_file_as(self) -> bool:
        editor = self._current_editor()
        if editor is None:
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
        self.statusBar().showMessage(f"Saved {absolute_target}", 2500)
        self.log(f"[editor] Saved file: {absolute_target}")
        if large_file_mode:
            self.log(f"[editor] Large File Mode active ({large_file_reason})")
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
        editor.setPlainText(content)
        editor.document().setModified(False)
        editor.setProperty("file_path", os.path.abspath(file_path) if file_path else None)
        editor.setProperty("display_name", display_name)
        editor.setProperty("large_file_mode", large_file_mode)
        editor.setProperty("large_file_mode_reason", large_file_reason)
        editor.setProperty("autosave_token", f"editor-{id(editor):x}")
        editor.configure_syntax_highlighting(file_path, large_file_mode)
        editor.document().modificationChanged.connect(lambda _v, e=editor: self._update_editor_tab_title(e))
        editor.textChanged.connect(lambda e=editor: self._on_editor_text_changed(e))
        return editor

    def _on_editor_text_changed(self, editor: CodeEditor) -> None:
        if self.find_panel.isVisible() and editor is self._current_editor():
            self._refresh_find_highlights()

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

    def _update_editor_mode_status(self, editor: CodeEditor | None) -> None:
        if editor is None:
            self.language_status_label.setText("Plain Text")
            self.large_file_status_label.setText("")
            self.large_file_status_label.setToolTip("")
            return

        self.language_status_label.setText(editor.language_display_name())
        if editor.is_large_file_mode():
            reason_value = editor.property("large_file_mode_reason")
            reason = reason_value if isinstance(reason_value, str) else ""
            self.large_file_status_label.setText("Large File Mode")
            self.large_file_status_label.setToolTip(reason or "Large file optimizations enabled.")
        else:
            self.large_file_status_label.setText("")
            self.large_file_status_label.setToolTip("")

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
                "bottom_panel_layout": self._BOTTOM_LAYOUT_STACKED,
                "output_enabled": True,
                "terminal_enabled": True,
                "window": {
                    "use_last_size": False,
                },
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
            return self._bottom_layout_mode

        ui_payload = payload.get("ui")
        if not isinstance(ui_payload, dict):
            return self._bottom_layout_mode

        layout_value = ui_payload.get("bottom_panel_layout")
        if layout_value in {self._BOTTOM_LAYOUT_STACKED, self._BOTTOM_LAYOUT_SIDE_BY_SIDE}:
            return layout_value

        if layout_value is not None:
            self.log("[settings] Invalid ui.bottom_panel_layout; keeping current layout.")
        return self._bottom_layout_mode

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
        use_side_by_side = layout_mode == self._BOTTOM_LAYOUT_SIDE_BY_SIDE
        self.bottom_layout_stacked_action.blockSignals(True)
        self.bottom_layout_side_by_side_action.blockSignals(True)
        self.bottom_layout_stacked_action.setChecked(not use_side_by_side)
        self.bottom_layout_side_by_side_action.setChecked(use_side_by_side)
        self.bottom_layout_stacked_action.blockSignals(False)
        self.bottom_layout_side_by_side_action.blockSignals(False)
        self._set_bottom_dock_layout(layout_mode, persist=False)

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
        ui_payload["bottom_panel_layout"] = self._bottom_layout_mode
        ui_payload["output_enabled"] = self.output_dock.isVisible()
        ui_payload["terminal_enabled"] = self.terminal_dock.isVisible()
        if not (self.isFullScreen() or self.isMaximized() or self.isMinimized()):
            current_width = max(self._MIN_WINDOW_WIDTH, int(self.width()))
            current_height = max(self._MIN_WINDOW_HEIGHT, int(self.height()))
            window_payload = ui_payload.get("window")
            if not isinstance(window_payload, dict):
                window_payload = {}
            window_payload["use_last_size"] = True
            window_payload["width"] = current_width
            window_payload["height"] = current_height
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
        for editor in self._open_editors():
            file_path = self._editor_file_path(editor)
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
            self.log(f"[watcher] Workspace updated externally: {absolute_changed}")
            self.statusBar().showMessage("Workspace tree refreshed from external changes.", 1800)
        self._sync_file_watcher_paths()

    def _on_watched_file_changed(self, changed_path: str) -> None:
        self._handle_external_file_change(changed_path, source="watcher")
        self._sync_file_watcher_paths()

    def _poll_watched_files(self) -> None:
        if not self._open_editors_by_path:
            self._prune_recent_internal_writes()
            return

        for editor in self._open_editors():
            file_path = self._editor_file_path(editor)
            if not file_path:
                continue
            self._handle_external_file_change(file_path, source="poll")

    def _handle_external_file_change(self, file_path: str, source: str) -> None:
        absolute_path = os.path.abspath(file_path)
        key = self._normalize_path(absolute_path)
        editor = self._open_editors_by_path.get(key)
        if editor is None:
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

        if key in self._external_change_prompts:
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

        max_position = max(0, editor.document().characterCount() - 1)
        cursor = editor.textCursor()
        cursor.setPosition(min(cursor_position, max_position))
        editor.setTextCursor(cursor)
        editor.verticalScrollBar().setValue(min(scroll_value, editor.verticalScrollBar().maximum()))

        self._update_editor_tab_title(editor)
        if editor is self._current_editor():
            self._update_editor_mode_status(editor)
            self._refresh_breadcrumbs(editor)
            if self.find_panel.isVisible():
                self._refresh_find_highlights()

        self._record_file_disk_state(absolute_path)
        self.statusBar().showMessage(f"Reloaded {absolute_path} ({reason}).", 2500)
        self.log(f"[watcher] Reloaded file from disk: {absolute_path} ({reason}).")
        return True

    def _request_close_tab(self, tabs: QTabWidget, tab_index: int) -> None:
        editor = self._editor_at(tabs, tab_index)
        if editor is None:
            return

        self._set_active_tab_widget(tabs)
        if not self._confirm_close_editor(editor):
            return

        self._close_editor_tab(tabs, tab_index)

    def _close_editor_tab(self, tabs: QTabWidget, tab_index: int) -> None:
        editor = self._editor_at(tabs, tab_index)
        if editor is None:
            return

        file_path = self._editor_file_path(editor)
        if file_path:
            key = self._normalize_path(file_path)
            self._open_editors_by_path.pop(key, None)
            self._file_disk_state.pop(key, None)
            self._recent_internal_writes.pop(key, None)

        if self._find_highlight_editor is editor:
            self._find_highlight_editor = None

        tabs.removeTab(tab_index)
        editor.deleteLater()
        self._sync_file_watcher_paths()
        self._update_editor_surface()
        self._refresh_welcome_recent_list()

        if tabs.count() == 0 and self._active_editor_tabs is tabs:
            self._active_editor_tabs = self.primary_tabs if tabs is self.secondary_tabs else tabs

    def _confirm_close_editor(self, editor: CodeEditor) -> bool:
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
            editor = self._editor_at(self.secondary_tabs, 0)
            if editor is None:
                self.secondary_tabs.removeTab(0)
                continue

            title = self.secondary_tabs.tabText(0)
            tooltip = self.secondary_tabs.tabToolTip(0)
            self.secondary_tabs.removeTab(0)

            new_index = self.primary_tabs.addTab(editor, title)
            self.primary_tabs.setTabToolTip(new_index, tooltip)

        self.secondary_tabs.hide()
        self._set_active_tab_widget(self.primary_tabs)
        self.log("[editor] Split view disabled")
        self._update_editor_surface()

    def move_current_tab_to_other_split(self) -> None:
        current_tabs = self._active_editor_tabs or self.primary_tabs
        editor = self._current_editor(current_tabs)
        if editor is None:
            return

        if not self.secondary_tabs.isVisible():
            self.split_toggle_action.setChecked(True)

        target_tabs = self.secondary_tabs if current_tabs is self.primary_tabs else self.primary_tabs
        tab_index = current_tabs.indexOf(editor)
        if tab_index < 0:
            return

        title = current_tabs.tabText(tab_index)
        tooltip = current_tabs.tabToolTip(tab_index)
        current_tabs.removeTab(tab_index)

        new_index = target_tabs.addTab(editor, title)
        target_tabs.setTabToolTip(new_index, tooltip)
        target_tabs.setCurrentIndex(new_index)
        self._set_active_tab_widget(target_tabs)
        editor.setFocus()
        self._refresh_breadcrumbs(editor)
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
        editor = self._editor_at(tabs, tab_index)
        if editor is None:
            self._update_editor_surface()
            self._update_editor_mode_status(None)
            self._refresh_breadcrumbs(None)
            if self.find_panel.isVisible():
                self._refresh_find_highlights()
            return

        file_path = self._editor_file_path(editor)
        if file_path:
            self._reveal_path(file_path)
        self._update_editor_mode_status(editor)
        self._refresh_breadcrumbs(editor)
        self._update_editor_surface()
        if self.find_panel.isVisible():
            self._refresh_find_highlights()

    def _set_active_tab_widget(self, tabs: QTabWidget) -> None:
        self._active_editor_tabs = tabs
        self._refresh_breadcrumbs(self._current_editor(tabs))

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

    def _update_editor_tab_title(self, editor: CodeEditor) -> None:
        tabs = self._find_tab_widget_for_editor(editor)
        if tabs is None:
            return

        tab_index = tabs.indexOf(editor)
        if tab_index < 0:
            return

        display_name = self._editor_display_name(editor)
        dirty_prefix = "*" if editor.document().isModified() else ""
        tabs.setTabText(tab_index, f"{dirty_prefix}{display_name}")

        file_path = self._editor_file_path(editor)
        tabs.setTabToolTip(tab_index, file_path or display_name)

    def _update_open_tabs_after_rename(self, old_path: str, new_path: str) -> None:
        old_key = self._normalize_path(old_path)
        direct_editor = self._open_editors_by_path.pop(old_key, None)
        if direct_editor is not None:
            self._apply_new_editor_path(direct_editor, new_path)
            return

        moved_editors: list[tuple[CodeEditor, str]] = []
        for editor in self._open_editors_by_path.values():
            file_path_value = self._editor_file_path(editor)
            if file_path_value and self._is_same_or_child(file_path_value, old_path):
                relative = os.path.relpath(file_path_value, old_path)
                moved_editors.append((editor, os.path.join(new_path, relative)))

        for editor, updated_path in moved_editors:
            old_editor_path = self._editor_file_path(editor)
            if old_editor_path:
                self._open_editors_by_path.pop(self._normalize_path(old_editor_path), None)
            self._apply_new_editor_path(editor, updated_path)

    def _apply_new_editor_path(self, editor: CodeEditor, new_path: str) -> None:
        old_path = self._editor_file_path(editor)
        absolute_path = os.path.abspath(new_path)
        editor.setProperty("file_path", absolute_path)
        large_file_mode = bool(editor.property("large_file_mode"))
        editor.configure_syntax_highlighting(absolute_path, large_file_mode)
        if old_path:
            old_key = self._normalize_path(old_path)
            self._file_disk_state.pop(old_key, None)
            self._recent_internal_writes.pop(old_key, None)

        new_key = self._normalize_path(absolute_path)
        self._open_editors_by_path[new_key] = editor
        self._record_file_disk_state(absolute_path)
        self._sync_file_watcher_paths()
        self._update_editor_tab_title(editor)
        if editor is self._current_editor():
            self._update_editor_mode_status(editor)
            self._refresh_breadcrumbs(editor)

    def _close_tabs_for_deleted_path(self, deleted_path: str) -> None:
        for tabs in self._all_tab_widgets():
            for index in reversed(range(tabs.count())):
                editor = self._editor_at(tabs, index)
                if editor is None:
                    continue
                file_path = self._editor_file_path(editor)
                if file_path and self._is_same_or_child(file_path, deleted_path):
                    self._close_editor_tab(tabs, index)

    def _find_tab_widget_for_editor(self, editor: CodeEditor) -> QTabWidget | None:
        for tabs in self._all_tab_widgets():
            if tabs.indexOf(editor) >= 0:
                return tabs
        return None

    def _all_tab_widgets(self) -> tuple[QTabWidget, QTabWidget]:
        return self.primary_tabs, self.secondary_tabs

    def _editor_at(self, tabs: QTabWidget, tab_index: int) -> CodeEditor | None:
        widget = tabs.widget(tab_index)
        if isinstance(widget, CodeEditor):
            return widget
        return None

    def _current_editor(self, tabs: QTabWidget | None = None) -> CodeEditor | None:
        active_tabs = tabs or self._active_editor_tabs or self.primary_tabs
        editor = self._editor_at(active_tabs, active_tabs.currentIndex())
        if editor is not None:
            return editor

        for tab_widget in self._all_tab_widgets():
            editor = self._editor_at(tab_widget, tab_widget.currentIndex())
            if editor is not None:
                return editor
        return None

    def _editor_file_path(self, editor: CodeEditor) -> str | None:
        value = editor.property("file_path")
        if isinstance(value, str) and value:
            return value
        return None

    def _editor_display_name(self, editor: CodeEditor) -> str:
        file_path = self._editor_file_path(editor)
        if file_path:
            return os.path.basename(file_path)

        display_name = editor.property("display_name")
        if isinstance(display_name, str) and display_name:
            return display_name
        return "Untitled"

    def _close_all_open_editors(self) -> bool:
        for tabs in self._all_tab_widgets():
            for index in reversed(range(tabs.count())):
                editor = self._editor_at(tabs, index)
                if editor is None:
                    continue
                if not self._confirm_close_editor(editor):
                    return False
                self._close_editor_tab(tabs, index)
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API)
        self._is_app_closing = True
        self._autosave_timer.stop()
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
