from __future__ import annotations

import locale
import os

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class CmdTerminalWidget(QPlainTextEdit):
    session_started = Signal(str)
    session_error = Signal(str)
    session_exited = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("terminalConsole")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setUndoRedoEnabled(False)

        self._encoding = locale.getpreferredencoding(False) or "utf-8"
        self._working_directory = os.getcwd()
        self._input_anchor = 0

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyRead.connect(self._on_ready_read)
        self._process.started.connect(self._on_process_started)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)

        self.start_shell(self._working_directory)

    def set_working_directory(self, working_directory: str) -> None:
        normalized = os.path.abspath(working_directory)
        if not os.path.isdir(normalized):
            normalized = os.getcwd()

        if os.path.normcase(normalized) == os.path.normcase(self._working_directory):
            return

        self._working_directory = normalized
        self.start_shell(self._working_directory)

    def start_shell(self, working_directory: str | None = None) -> None:
        if working_directory is not None:
            normalized = os.path.abspath(working_directory)
            if os.path.isdir(normalized):
                self._working_directory = normalized
            else:
                self._working_directory = os.getcwd()

        self.shutdown()
        self.clear()
        self._input_anchor = 0
        self._process.setWorkingDirectory(self._working_directory)
        self._process.start("cmd.exe", ["/Q"])

    def shutdown(self, timeout_ms: int = 2000) -> bool:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return True

        self._process.write(b"exit\r\n")
        if self._process.waitForFinished(timeout_ms):
            return True

        self._process.kill()
        return self._process.waitForFinished(timeout_ms)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API)
        if event.matches(QKeySequence.StandardKey.Copy) or event.matches(QKeySequence.StandardKey.SelectAll):
            super().keyPressEvent(event)
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C:
            if self.textCursor().hasSelection():
                super().keyPressEvent(event)
            elif self._process.state() == QProcess.ProcessState.Running:
                self._process.write(b"\x03")
            return

        self._coerce_cursor_to_input_region()
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            command = self._current_input_text()
            super().keyPressEvent(event)
            self._input_anchor = len(self.toPlainText())
            if self._process.state() == QProcess.ProcessState.Running:
                payload = (command + "\r\n").encode(self._encoding, errors="replace")
                self._process.write(payload)
            return

        cursor = self.textCursor()
        if key == Qt.Key.Key_Backspace and cursor.position() <= self._input_anchor:
            return
        if key == Qt.Key.Key_Left and cursor.position() <= self._input_anchor:
            return
        if key == Qt.Key.Key_Home:
            cursor.setPosition(self._input_anchor)
            self.setTextCursor(cursor)
            return
        if key == Qt.Key.Key_Delete and cursor.position() < self._input_anchor:
            return

        super().keyPressEvent(event)

    def _coerce_cursor_to_input_region(self) -> None:
        cursor = self.textCursor()
        if cursor.selectionStart() < self._input_anchor:
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            return

        if cursor.position() < self._input_anchor:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

    def _current_input_text(self) -> str:
        text = self.toPlainText()
        if self._input_anchor >= len(text):
            return ""
        return text[self._input_anchor:]

    def _append_output(self, text: str) -> None:
        if not text:
            return

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        cursor = self.textCursor()
        at_end = cursor.position() >= len(self.toPlainText())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(normalized)
        self._input_anchor = len(self.toPlainText())

        if at_end:
            self.moveCursor(QTextCursor.MoveOperation.End)

    def _on_ready_read(self) -> None:
        raw = bytes(self._process.readAll())
        if not raw:
            return
        text = raw.decode(self._encoding, errors="replace")
        self._append_output(text)

    def _on_process_started(self) -> None:
        self.session_started.emit(self._working_directory)

    def _on_process_error(self, process_error: QProcess.ProcessError) -> None:
        message = f"Terminal process error: {process_error}"
        self._append_output(f"\n{message}\n")
        self.session_error.emit(message)

    def _on_process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._append_output(f"\n[cmd exited with code {exit_code}]\n")
        self.session_exited.emit(exit_code)
