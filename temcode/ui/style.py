from __future__ import annotations


VS_DARK_STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI";
    font-size: 10pt;
}

QMainWindow::separator {
    background: #2d2d30;
    width: 1px;
    height: 1px;
}

QMenuBar {
    background-color: #2d2d30;
    color: #f0f0f0;
    border-bottom: 1px solid #3f3f46;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
}

QMenuBar::item:selected {
    background: #3e3e42;
}

QMenu {
    background-color: #252526;
    border: 1px solid #3f3f46;
    color: #f0f0f0;
}

QMenu::item:selected {
    background-color: #094771;
}

QStatusBar {
    background-color: #252526;
    color: #d4d4d4;
    border-top: 1px solid #3f3f46;
}

QLabel#autosaveStatusLabel {
    color: #c8c8c8;
    padding-right: 12px;
}

QDockWidget#terminalDock QPlainTextEdit#terminalConsole {
    background-color: #121212;
    border: 1px solid #3f3f46;
    color: #d9f2ff;
    font-family: "Consolas";
    font-size: 10pt;
}

QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}

QDockWidget::title {
    background: #2d2d30;
    color: #d4d4d4;
    padding: 6px 8px;
    border-bottom: 1px solid #3f3f46;
}

QTreeWidget, QPlainTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #3f3f46;
    selection-background-color: #094771;
    selection-color: #ffffff;
}

QTreeView::item:hover,
QTreeWidget::item:hover {
    background: #2a2d2e;
}

QTreeView::item:selected,
QTreeWidget::item:selected {
    background: #094771;
    color: #ffffff;
}

QFrame#breadcrumbsBar {
    background: #252526;
    border-top: 1px solid #2d2d30;
    border-bottom: 1px solid #3f3f46;
}

QLabel#breadcrumbSegment {
    color: #c8c8c8;
    padding: 0 2px;
}

QLabel#breadcrumbSeparator {
    color: #6e7681;
    padding: 0 1px;
}

QLabel#editorPlaceholder {
    color: #808080;
    font-size: 16pt;
    border: 1px dashed #3f3f46;
    margin: 8px;
}

QLabel#solutionExplorerPlaceholder {
    color: #909090;
    padding: 14px;
}

QFrame#welcomeScreen {
    border: 1px solid #3f3f46;
    border-radius: 8px;
    margin: 16px;
    background: #202022;
}

QLabel#welcomeTitle {
    font-size: 20pt;
    font-weight: 600;
    color: #f0f0f0;
}

QLabel#welcomeSubtitle {
    font-size: 10pt;
    color: #b0b0b0;
}

QLabel#welcomeRecentLabel {
    font-size: 10pt;
    font-weight: 600;
    color: #d4d4d4;
    margin-top: 8px;
}

QListWidget#welcomeRecentList {
    background: #1c1c1c;
    border: 1px solid #3f3f46;
    color: #d4d4d4;
    padding: 4px;
}

QListWidget#welcomeRecentList::item {
    padding: 6px 8px;
}

QListWidget#welcomeRecentList::item:selected {
    background: #3a3d41;
    color: #ffffff;
}

QPushButton#welcomeActionButton {
    background: #2f3237;
    border: 1px solid #4a4d52;
    padding: 6px 12px;
}

QPushButton#welcomeActionButton:hover {
    background: #3a3d41;
}
"""
