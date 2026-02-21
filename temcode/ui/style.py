from __future__ import annotations


DEFAULT_THEME_ID = "dark"

_THEME_DISPLAY_NAMES: dict[str, str] = {
    "dark": "Default Dark",
    "light": "Slate Light",
    "nord": "Nord Blue",
    "forest": "Forest Night",
    "colorful": "Colorful",
}

_THEME_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "widget_bg": "#1e1e1e",
        "widget_fg": "#d4d4d4",
        "separator_bg": "#2d2d30",
        "menubar_bg": "#2d2d30",
        "menubar_fg": "#f0f0f0",
        "menubar_border": "#3f3f46",
        "menubar_item_hover": "#3e3e42",
        "menu_bg": "#252526",
        "menu_border": "#3f3f46",
        "menu_fg": "#f0f0f0",
        "menu_item_hover": "#094771",
        "status_bg": "#252526",
        "status_fg": "#d4d4d4",
        "status_border": "#3f3f46",
        "autosave_fg": "#c8c8c8",
        "terminal_bg": "#121212",
        "terminal_border": "#3f3f46",
        "terminal_fg": "#d9f2ff",
        "dock_title_bg": "#2d2d30",
        "dock_title_fg": "#d4d4d4",
        "dock_title_border": "#3f3f46",
        "editor_bg": "#1e1e1e",
        "editor_border": "#3f3f46",
        "selection_bg": "#094771",
        "selection_fg": "#ffffff",
        "tree_hover_bg": "#2a2d2e",
        "tree_selected_bg": "#094771",
        "breadcrumbs_bg": "#252526",
        "breadcrumbs_border_top": "#2d2d30",
        "breadcrumbs_border_bottom": "#3f3f46",
        "breadcrumb_fg": "#c8c8c8",
        "breadcrumb_sep_fg": "#6e7681",
        "placeholder_fg": "#808080",
        "placeholder_border": "#3f3f46",
        "solution_placeholder_fg": "#909090",
        "welcome_bg": "#202022",
        "welcome_border": "#3f3f46",
        "welcome_title_fg": "#f0f0f0",
        "welcome_subtitle_fg": "#b0b0b0",
        "welcome_recent_fg": "#d4d4d4",
        "welcome_list_bg": "#1c1c1c",
        "welcome_list_border": "#3f3f46",
        "welcome_list_fg": "#d4d4d4",
        "welcome_list_selected_bg": "#3a3d41",
        "welcome_list_selected_fg": "#ffffff",
        "button_bg": "#2f3237",
        "button_border": "#4a4d52",
        "button_hover_bg": "#3a3d41",
        "tab_bar_bg": "#202124",
        "tab_border": "#3f3f46",
        "tab_inactive_bg": "#2a2d32",
        "tab_inactive_fg": "#aeb6c2",
        "tab_hover_bg": "#333840",
        "tab_active_bg": "#1e1e1e",
        "tab_active_fg": "#f5f7fa",
        "tab_close_fg": "#8a94a3",
        "tab_close_hover_fg": "#dbe2ef",
        "tab_close_hover_bg": "#3a4352",
        "tab_close_pressed_bg": "#4a5568",
        "scrollbar_track": "#252526",
        "scrollbar_handle": "#4f5560",
        "scrollbar_handle_hover": "#68717f",
        "scrollbar_handle_pressed": "#7a8597",
        "scrollbar_corner": "#1e1e1e",
    },
    "light": {
        "widget_bg": "#f4f6f8",
        "widget_fg": "#1f2328",
        "separator_bg": "#c7ced6",
        "menubar_bg": "#e9edf2",
        "menubar_fg": "#1f2328",
        "menubar_border": "#c7ced6",
        "menubar_item_hover": "#d7dee7",
        "menu_bg": "#ffffff",
        "menu_border": "#c7ced6",
        "menu_fg": "#1f2328",
        "menu_item_hover": "#dbeafe",
        "status_bg": "#eef2f6",
        "status_fg": "#1f2328",
        "status_border": "#c7ced6",
        "autosave_fg": "#475569",
        "terminal_bg": "#fafafa",
        "terminal_border": "#c7ced6",
        "terminal_fg": "#111827",
        "dock_title_bg": "#e9edf2",
        "dock_title_fg": "#1f2328",
        "dock_title_border": "#c7ced6",
        "editor_bg": "#ffffff",
        "editor_border": "#c7ced6",
        "selection_bg": "#b6d6ff",
        "selection_fg": "#111827",
        "tree_hover_bg": "#eef3f8",
        "tree_selected_bg": "#c9def7",
        "breadcrumbs_bg": "#eef2f6",
        "breadcrumbs_border_top": "#dbe2ea",
        "breadcrumbs_border_bottom": "#c7ced6",
        "breadcrumb_fg": "#334155",
        "breadcrumb_sep_fg": "#64748b",
        "placeholder_fg": "#64748b",
        "placeholder_border": "#94a3b8",
        "solution_placeholder_fg": "#64748b",
        "welcome_bg": "#ffffff",
        "welcome_border": "#c7ced6",
        "welcome_title_fg": "#111827",
        "welcome_subtitle_fg": "#475569",
        "welcome_recent_fg": "#1f2937",
        "welcome_list_bg": "#f8fafc",
        "welcome_list_border": "#c7ced6",
        "welcome_list_fg": "#1f2937",
        "welcome_list_selected_bg": "#dbeafe",
        "welcome_list_selected_fg": "#111827",
        "button_bg": "#e5eaf0",
        "button_border": "#bec7d2",
        "button_hover_bg": "#d3dde7",
        "tab_bar_bg": "#e8edf3",
        "tab_border": "#c7ced6",
        "tab_inactive_bg": "#e2e8f0",
        "tab_inactive_fg": "#475569",
        "tab_hover_bg": "#d8e1ec",
        "tab_active_bg": "#ffffff",
        "tab_active_fg": "#0f172a",
        "tab_close_fg": "#6b7280",
        "tab_close_hover_fg": "#334155",
        "tab_close_hover_bg": "#d2dbe7",
        "tab_close_pressed_bg": "#c2cedc",
        "scrollbar_track": "#e6ebf1",
        "scrollbar_handle": "#a8b6c6",
        "scrollbar_handle_hover": "#8ea1b7",
        "scrollbar_handle_pressed": "#788ea8",
        "scrollbar_corner": "#f4f6f8",
    },
    "nord": {
        "widget_bg": "#2e3440",
        "widget_fg": "#e5e9f0",
        "separator_bg": "#3b4252",
        "menubar_bg": "#3b4252",
        "menubar_fg": "#eceff4",
        "menubar_border": "#4c566a",
        "menubar_item_hover": "#434c5e",
        "menu_bg": "#323a48",
        "menu_border": "#4c566a",
        "menu_fg": "#eceff4",
        "menu_item_hover": "#5e81ac",
        "status_bg": "#323a48",
        "status_fg": "#e5e9f0",
        "status_border": "#4c566a",
        "autosave_fg": "#d8dee9",
        "terminal_bg": "#242933",
        "terminal_border": "#4c566a",
        "terminal_fg": "#cfe3ff",
        "dock_title_bg": "#3b4252",
        "dock_title_fg": "#e5e9f0",
        "dock_title_border": "#4c566a",
        "editor_bg": "#2e3440",
        "editor_border": "#4c566a",
        "selection_bg": "#5e81ac",
        "selection_fg": "#ffffff",
        "tree_hover_bg": "#3c4455",
        "tree_selected_bg": "#5e81ac",
        "breadcrumbs_bg": "#323a48",
        "breadcrumbs_border_top": "#3b4252",
        "breadcrumbs_border_bottom": "#4c566a",
        "breadcrumb_fg": "#d8dee9",
        "breadcrumb_sep_fg": "#8f9db3",
        "placeholder_fg": "#8f9db3",
        "placeholder_border": "#4c566a",
        "solution_placeholder_fg": "#9aa7ba",
        "welcome_bg": "#2f3645",
        "welcome_border": "#4c566a",
        "welcome_title_fg": "#eceff4",
        "welcome_subtitle_fg": "#c7d1df",
        "welcome_recent_fg": "#e5e9f0",
        "welcome_list_bg": "#2a313e",
        "welcome_list_border": "#4c566a",
        "welcome_list_fg": "#e5e9f0",
        "welcome_list_selected_bg": "#4a5f7d",
        "welcome_list_selected_fg": "#ffffff",
        "button_bg": "#3f4757",
        "button_border": "#5b6579",
        "button_hover_bg": "#4a566a",
        "tab_bar_bg": "#323a48",
        "tab_border": "#4c566a",
        "tab_inactive_bg": "#3b4455",
        "tab_inactive_fg": "#c9d2de",
        "tab_hover_bg": "#445066",
        "tab_active_bg": "#2e3440",
        "tab_active_fg": "#eceff4",
        "tab_close_fg": "#94a3b8",
        "tab_close_hover_fg": "#e5e9f0",
        "tab_close_hover_bg": "#55637c",
        "tab_close_pressed_bg": "#65748f",
        "scrollbar_track": "#3b4252",
        "scrollbar_handle": "#67758b",
        "scrollbar_handle_hover": "#7d8ca3",
        "scrollbar_handle_pressed": "#95a7c0",
        "scrollbar_corner": "#2e3440",
    },
    "forest": {
        "widget_bg": "#1d2521",
        "widget_fg": "#d7e2db",
        "separator_bg": "#27332d",
        "menubar_bg": "#27332d",
        "menubar_fg": "#e4efe8",
        "menubar_border": "#395145",
        "menubar_item_hover": "#314139",
        "menu_bg": "#232e28",
        "menu_border": "#395145",
        "menu_fg": "#e4efe8",
        "menu_item_hover": "#2f7a5d",
        "status_bg": "#232e28",
        "status_fg": "#d7e2db",
        "status_border": "#395145",
        "autosave_fg": "#c1d5c9",
        "terminal_bg": "#18201c",
        "terminal_border": "#395145",
        "terminal_fg": "#d8f6e4",
        "dock_title_bg": "#27332d",
        "dock_title_fg": "#d7e2db",
        "dock_title_border": "#395145",
        "editor_bg": "#1d2521",
        "editor_border": "#395145",
        "selection_bg": "#2f7a5d",
        "selection_fg": "#ffffff",
        "tree_hover_bg": "#2a3730",
        "tree_selected_bg": "#2f7a5d",
        "breadcrumbs_bg": "#232e28",
        "breadcrumbs_border_top": "#27332d",
        "breadcrumbs_border_bottom": "#395145",
        "breadcrumb_fg": "#c1d5c9",
        "breadcrumb_sep_fg": "#7f9a8a",
        "placeholder_fg": "#7f9a8a",
        "placeholder_border": "#395145",
        "solution_placeholder_fg": "#8ea698",
        "welcome_bg": "#212b25",
        "welcome_border": "#395145",
        "welcome_title_fg": "#e4efe8",
        "welcome_subtitle_fg": "#b9ccbe",
        "welcome_recent_fg": "#d7e2db",
        "welcome_list_bg": "#1a231f",
        "welcome_list_border": "#395145",
        "welcome_list_fg": "#d7e2db",
        "welcome_list_selected_bg": "#386c56",
        "welcome_list_selected_fg": "#ffffff",
        "button_bg": "#304038",
        "button_border": "#4b6659",
        "button_hover_bg": "#3a4e44",
        "tab_bar_bg": "#232e28",
        "tab_border": "#395145",
        "tab_inactive_bg": "#2b3932",
        "tab_inactive_fg": "#b9ccbe",
        "tab_hover_bg": "#33453c",
        "tab_active_bg": "#1d2521",
        "tab_active_fg": "#e4efe8",
        "tab_close_fg": "#96af9f",
        "tab_close_hover_fg": "#e4efe8",
        "tab_close_hover_bg": "#466154",
        "tab_close_pressed_bg": "#557668",
        "scrollbar_track": "#27332d",
        "scrollbar_handle": "#4f6c60",
        "scrollbar_handle_hover": "#628679",
        "scrollbar_handle_pressed": "#78a08f",
        "scrollbar_corner": "#1d2521",
    },
    "colorful": {
        "widget_bg": "#19172b",
        "widget_fg": "#f7f7ff",
        "separator_bg": "#44407a",
        "menubar_bg": "#2b2054",
        "menubar_fg": "#fefbff",
        "menubar_border": "#6a5acd",
        "menubar_item_hover": "#ff6aa2",
        "menu_bg": "#30235f",
        "menu_border": "#6a5acd",
        "menu_fg": "#f9f6ff",
        "menu_item_hover": "#ff9f1c",
        "status_bg": "#22243d",
        "status_fg": "#d7f6ff",
        "status_border": "#2ec4b6",
        "autosave_fg": "#ffd166",
        "terminal_bg": "#0f1a2f",
        "terminal_border": "#2ec4b6",
        "terminal_fg": "#9bf6ff",
        "dock_title_bg": "#25305f",
        "dock_title_fg": "#ecf3ff",
        "dock_title_border": "#4cc9f0",
        "editor_bg": "#15152a",
        "editor_border": "#5a4db2",
        "selection_bg": "#f15bb5",
        "selection_fg": "#1a1025",
        "tree_hover_bg": "#2b2950",
        "tree_selected_bg": "#00bbf9",
        "breadcrumbs_bg": "#2a214f",
        "breadcrumbs_border_top": "#40367a",
        "breadcrumbs_border_bottom": "#6750c7",
        "breadcrumb_fg": "#f4e8ff",
        "breadcrumb_sep_fg": "#b8a8ff",
        "placeholder_fg": "#9fa7d4",
        "placeholder_border": "#6f6ac7",
        "solution_placeholder_fg": "#b0badf",
        "welcome_bg": "#201b3f",
        "welcome_border": "#6750c7",
        "welcome_title_fg": "#fff3ff",
        "welcome_subtitle_fg": "#f2c3ff",
        "welcome_recent_fg": "#ffd6a5",
        "welcome_list_bg": "#181733",
        "welcome_list_border": "#6750c7",
        "welcome_list_fg": "#e4e9ff",
        "welcome_list_selected_bg": "#00bbf9",
        "welcome_list_selected_fg": "#091223",
        "button_bg": "#ff4d6d",
        "button_border": "#ff8fa3",
        "button_hover_bg": "#ff758f",
        "tab_bar_bg": "#231b45",
        "tab_border": "#6b5bd6",
        "tab_inactive_bg": "#342a67",
        "tab_inactive_fg": "#d8d1ff",
        "tab_hover_bg": "#4a3d8a",
        "tab_active_bg": "#00c2a8",
        "tab_active_fg": "#062721",
        "tab_close_fg": "#ff3b3b",
        "tab_close_hover_fg": "#ffffff",
        "tab_close_hover_bg": "#ff1744",
        "tab_close_pressed_bg": "#d50000",
        "scrollbar_track": "#251f4a",
        "scrollbar_handle": "#8a6dff",
        "scrollbar_handle_hover": "#b197ff",
        "scrollbar_handle_pressed": "#cdbaff",
        "scrollbar_corner": "#19172b",
    },
}


def _format_css_number(value: float) -> str:
    rounded = round(value, 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _build_stylesheet(colors: dict[str, str], ui_zoom_percent: int = 100) -> str:
    try:
        zoom_value = int(ui_zoom_percent)
    except (TypeError, ValueError):
        zoom_value = 100
    clamped_zoom = max(70, min(300, zoom_value))
    zoom_ratio = clamped_zoom / 100.0

    def pt(base_size: float) -> str:
        return f"{_format_css_number(max(1.0, base_size * zoom_ratio))}pt"

    return f"""
QWidget {{
    background-color: {colors["widget_bg"]};
    color: {colors["widget_fg"]};
    font-family: "Segoe UI";
    font-size: {pt(10)};
}}

QMainWindow::separator {{
    background: {colors["separator_bg"]};
    width: 1px;
    height: 1px;
}}

QMenuBar {{
    background-color: {colors["menubar_bg"]};
    color: {colors["menubar_fg"]};
    border-bottom: 1px solid {colors["menubar_border"]};
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
}}

QMenuBar::item:selected {{
    background: {colors["menubar_item_hover"]};
}}

QMenu {{
    background-color: {colors["menu_bg"]};
    border: 1px solid {colors["menu_border"]};
    color: {colors["menu_fg"]};
}}

QMenu::item:selected {{
    background-color: {colors["menu_item_hover"]};
}}

QStatusBar {{
    background-color: {colors["status_bg"]};
    color: {colors["status_fg"]};
    border-top: 1px solid {colors["status_border"]};
}}

QLabel#autosaveStatusLabel {{
    color: {colors["autosave_fg"]};
    padding-right: 12px;
}}

QDockWidget#terminalDock QPlainTextEdit#terminalConsole {{
    background-color: {colors["terminal_bg"]};
    border: 1px solid {colors["terminal_border"]};
    color: {colors["terminal_fg"]};
    font-family: "Consolas";
    font-size: {pt(10)};
}}

QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background: {colors["dock_title_bg"]};
    color: {colors["dock_title_fg"]};
    padding: 6px 8px;
    border-bottom: 1px solid {colors["dock_title_border"]};
}}

QTabWidget::pane {{
    border: 1px solid {colors["editor_border"]};
    border-top: none;
}}

QTabBar {{
    background: {colors["tab_bar_bg"]};
}}

QTabBar::tab {{
    background: {colors["tab_inactive_bg"]};
    color: {colors["tab_inactive_fg"]};
    border: 1px solid {colors["tab_border"]};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 5px 8px;
    margin-right: 2px;
    min-height: 24px;
}}

QTabBar::tab:hover {{
    background: {colors["tab_hover_bg"]};
}}

QTabBar::tab:selected {{
    background: {colors["tab_active_bg"]};
    color: {colors["tab_active_fg"]};
}}

QTabBar::close-button {{
    width: 0px;
    height: 0px;
    margin: 0px;
    padding: 0px;
}}

QToolButton#editorTabCloseButton {{
    background: transparent;
    border: none;
    color: {colors["tab_close_fg"]};
    font-size: {pt(10)};
    font-weight: 700;
    padding: 0;
}}

QToolButton#editorTabCloseButton:hover {{
    color: {colors["tab_close_hover_fg"]};
    background: {colors["tab_close_hover_bg"]};
    border-radius: 7px;
}}

QToolButton#editorTabCloseButton:pressed {{
    color: {colors["tab_close_hover_fg"]};
    background: {colors["tab_close_pressed_bg"]};
    border-radius: 7px;
}}

QTreeWidget, QPlainTextEdit {{
    background-color: {colors["editor_bg"]};
    border: 1px solid {colors["editor_border"]};
    selection-background-color: {colors["selection_bg"]};
    selection-color: {colors["selection_fg"]};
}}

QTreeView::item:hover,
QTreeWidget::item:hover {{
    background: {colors["tree_hover_bg"]};
}}

QTreeView::item:selected,
QTreeWidget::item:selected {{
    background: {colors["tree_selected_bg"]};
    color: {colors["selection_fg"]};
}}

QFrame#breadcrumbsBar {{
    background: {colors["breadcrumbs_bg"]};
    border-top: 1px solid {colors["breadcrumbs_border_top"]};
    border-bottom: 1px solid {colors["breadcrumbs_border_bottom"]};
}}

QFrame#solutionNavBar {{
    background: {colors["dock_title_bg"]};
    border-right: 1px solid {colors["dock_title_border"]};
}}

QToolButton#solutionNavExplorerButton,
QToolButton#solutionNavSearchButton,
QToolButton#solutionNavGitButton,
QToolButton#solutionNavSettingsButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0px;
}}

QToolButton#solutionNavExplorerButton:hover,
QToolButton#solutionNavSearchButton:hover,
QToolButton#solutionNavGitButton:hover,
QToolButton#solutionNavSettingsButton:hover {{
    background: {colors["button_hover_bg"]};
}}

QToolButton#solutionNavExplorerButton:checked,
QToolButton#solutionNavGitButton:checked,
QToolButton#solutionNavSearchButton:checked {{
    background: {colors["button_bg"]};
    border-color: {colors["button_border"]};
}}

QWidget#solutionGitPage {{
    background: {colors["widget_bg"]};
}}

QLabel#gitSectionTitle {{
    font-size: {pt(10)};
    font-weight: 700;
    letter-spacing: 0.2px;
    padding: 1px 0 1px 1px;
}}

QWidget#solutionGitPage QComboBox#gitRepoCombo,
QWidget#solutionGitPage QComboBox#gitBranchCombo,
QWidget#solutionGitPage QLineEdit#gitNewBranchInput,
QWidget#solutionGitPage QLineEdit#gitCommitInput {{
    background: {colors["editor_bg"]};
    border: 1px solid {colors["button_border"]};
    border-radius: 4px;
    padding: 4px 7px;
}}

QWidget#solutionGitPage QLineEdit#gitCommitInput {{
    min-height: 24px;
}}

QWidget#solutionGitPage QPushButton {{
    background: {colors["button_bg"]};
    border: 1px solid {colors["button_border"]};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 22px;
}}

QWidget#solutionGitPage QPushButton:hover {{
    background: {colors["button_hover_bg"]};
}}

QWidget#solutionGitPage QPushButton:disabled {{
    color: {colors["placeholder_fg"]};
}}

QToolButton#gitCommitSplitButton {{
    background: {colors["selection_bg"]};
    color: {colors["selection_fg"]};
    border: 1px solid {colors["selection_bg"]};
    border-radius: 4px;
    padding: 4px 14px;
    min-height: 24px;
    font-weight: 600;
}}

QToolButton#gitCommitSplitButton:hover {{
    border-color: {colors["button_border"]};
}}

QToolButton#gitCommitSplitButton:pressed {{
    background: {colors["button_hover_bg"]};
    color: {colors["selection_fg"]};
}}

QToolButton#gitCommitSplitButton:disabled {{
    background: {colors["button_bg"]};
    border-color: {colors["button_border"]};
    color: {colors["placeholder_fg"]};
}}

QToolButton#gitCommitSplitButton::menu-button {{
    border-left: 1px solid {colors["button_border"]};
    width: 18px;
    padding: 0 2px;
}}

QListWidget#gitChangesList,
QListWidget#gitLogList {{
    background: {colors["editor_bg"]};
    border: 1px solid {colors["editor_border"]};
    border-radius: 4px;
    padding: 2px;
}}

QListWidget#gitChangesList::item,
QListWidget#gitLogList::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}

QListWidget#gitChangesList::item:selected,
QListWidget#gitLogList::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_fg"]};
}}

QLabel#breadcrumbSegment {{
    color: {colors["breadcrumb_fg"]};
    padding: 0 2px;
}}

QLabel#breadcrumbSeparator {{
    color: {colors["breadcrumb_sep_fg"]};
    padding: 0 1px;
}}

QPushButton#pythonRunButton {{
    background: {colors["button_bg"]};
    border: 1px solid {colors["button_border"]};
    padding: 2px 10px;
    min-height: 20px;
    border-radius: 4px;
}}

QPushButton#pythonRunButton:hover {{
    background: {colors["button_hover_bg"]};
}}

QLabel#editorPlaceholder {{
    color: {colors["placeholder_fg"]};
    font-size: {pt(16)};
    border: 1px dashed {colors["placeholder_border"]};
    margin: 8px;
}}

QLabel#solutionExplorerPlaceholder {{
    color: {colors["solution_placeholder_fg"]};
    padding: 14px;
}}

QFrame#welcomeScreen {{
    border: 1px solid {colors["welcome_border"]};
    border-radius: 8px;
    margin: 16px;
    background: {colors["welcome_bg"]};
}}

QLabel#welcomeTitle {{
    font-size: {pt(20)};
    font-weight: 600;
    color: {colors["welcome_title_fg"]};
}}

QLabel#welcomeSubtitle {{
    font-size: {pt(10)};
    color: {colors["welcome_subtitle_fg"]};
}}

QLabel#welcomeRecentLabel {{
    font-size: {pt(10)};
    font-weight: 600;
    color: {colors["welcome_recent_fg"]};
    margin-top: 8px;
}}

QListWidget#welcomeRecentList {{
    background: {colors["welcome_list_bg"]};
    border: 1px solid {colors["welcome_list_border"]};
    color: {colors["welcome_list_fg"]};
    padding: 4px;
}}

QListWidget#welcomeRecentList::item {{
    padding: 6px 8px;
}}

QListWidget#welcomeRecentList::item:selected {{
    background: {colors["welcome_list_selected_bg"]};
    color: {colors["welcome_list_selected_fg"]};
}}

QPushButton#welcomeActionButton {{
    background: {colors["button_bg"]};
    border: 1px solid {colors["button_border"]};
    padding: 6px 12px;
}}

QPushButton#welcomeActionButton:hover {{
    background: {colors["button_hover_bg"]};
}}

QScrollBar:vertical {{
    background: {colors["scrollbar_track"]};
    width: 12px;
    margin: 2px;
    border: none;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background: {colors["scrollbar_handle"]};
    border: none;
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {colors["scrollbar_handle_hover"]};
}}

QScrollBar::handle:vertical:pressed {{
    background: {colors["scrollbar_handle_pressed"]};
}}

QScrollBar::sub-line:vertical,
QScrollBar::add-line:vertical {{
    border: none;
    background: transparent;
    height: 0px;
}}

QScrollBar::sub-page:vertical,
QScrollBar::add-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: {colors["scrollbar_track"]};
    height: 12px;
    margin: 2px;
    border: none;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background: {colors["scrollbar_handle"]};
    border: none;
    border-radius: 6px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {colors["scrollbar_handle_hover"]};
}}

QScrollBar::handle:horizontal:pressed {{
    background: {colors["scrollbar_handle_pressed"]};
}}

QScrollBar::sub-line:horizontal,
QScrollBar::add-line:horizontal {{
    border: none;
    background: transparent;
    width: 0px;
}}

QScrollBar::sub-page:horizontal,
QScrollBar::add-page:horizontal {{
    background: transparent;
}}

QTableCornerButton::section {{
    background: {colors["scrollbar_corner"]};
    border: none;
}}
"""


THEME_STYLESHEETS: dict[str, str] = {
    theme_id: _build_stylesheet(palette, ui_zoom_percent=100)
    for theme_id, palette in _THEME_PALETTES.items()
}


def normalize_theme_id(theme_id: str | None) -> str:
    candidate = theme_id.strip().lower() if isinstance(theme_id, str) else ""
    if candidate in THEME_STYLESHEETS:
        return candidate
    return DEFAULT_THEME_ID


def available_theme_ids() -> tuple[str, ...]:
    return tuple(_THEME_DISPLAY_NAMES.keys())


def theme_display_name(theme_id: str | None) -> str:
    normalized = normalize_theme_id(theme_id)
    return _THEME_DISPLAY_NAMES.get(normalized, _THEME_DISPLAY_NAMES[DEFAULT_THEME_ID])


def theme_stylesheet_for(theme_id: str | None, ui_zoom_percent: int = 100) -> str:
    normalized = normalize_theme_id(theme_id)
    try:
        normalized_zoom = int(ui_zoom_percent)
    except (TypeError, ValueError):
        normalized_zoom = 100
    if normalized_zoom == 100:
        return THEME_STYLESHEETS[normalized]
    return _build_stylesheet(_THEME_PALETTES[normalized], ui_zoom_percent=normalized_zoom)


VS_DARK_STYLESHEET = THEME_STYLESHEETS[DEFAULT_THEME_ID]
