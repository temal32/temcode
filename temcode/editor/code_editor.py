from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QKeyEvent, QMouseEvent, QPainter, QTextCursor, QTextFormat, QWheelEvent
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from temcode.editor.highlighting import LANGUAGE_DISPLAY_NAMES, LanguageId, build_highlighter
from temcode.ui.style import DEFAULT_THEME_ID, normalize_theme_id


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._editor.line_number_area_paint_event(event)


class MinimapArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor
        self._drag_active = False

    def sizeHint(self) -> QSize:
        return QSize(self._editor.minimap_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._editor.minimap_area_paint_event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._editor.handle_minimap_interaction(event.position().y(), center=True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        if self._drag_active and (event.buttons() & Qt.MouseButton.LeftButton):
            self._editor.handle_minimap_interaction(event.position().y(), center=True)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = False
            self._editor.handle_minimap_interaction(event.position().y(), center=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CodeEditor(QPlainTextEdit):
    _OPENING_TO_CLOSING = {"(": ")", "[": "]", "{": "}"}
    _CLOSING_TO_OPENING = {")": "(", "]": "[", "}": "{"}
    _MIN_ZOOM_POINT_SIZE = 8.0
    _MAX_ZOOM_POINT_SIZE = 40.0
    _DEFAULT_THEME_COLORS = {
        "line_number_bg": "#252526",
        "line_number_active_fg": "#c8c8c8",
        "line_number_fg": "#6e7681",
        "current_line_bg": "#2a2d2e",
    }
    _SLATE_LIGHT_THEME_COLORS = {
        "line_number_bg": "#f3f6fa",
        "line_number_active_fg": "#0f172a",
        "line_number_fg": "#64748b",
        "current_line_bg": "#ffffff",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._indent_size = 4
        self._indent_unit = " " * self._indent_size
        self._bracket_scan_limit = 200_000
        self._minimap_width = 104
        self._minimap_density: list[float] = []
        self._minimap_normal_refresh_ms = 120
        self._minimap_large_refresh_ms = 900
        self._syntax_highlighter = None
        self._language_id = LanguageId.PLAIN_TEXT
        self._language_display_name = LANGUAGE_DISPLAY_NAMES[LanguageId.PLAIN_TEXT]
        self._large_file_mode = False
        self._theme_id = DEFAULT_THEME_ID

        self._line_number_area = LineNumberArea(self)
        self._minimap_area = MinimapArea(self)
        self._internal_extra_selections: list[QTextEdit.ExtraSelection] = []
        self._external_extra_selections: list[QTextEdit.ExtraSelection] = []
        self._minimap_refresh_timer = QTimer(self)
        self._minimap_refresh_timer.setSingleShot(True)
        self._minimap_refresh_timer.timeout.connect(self._rebuild_minimap_density)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(QFontMetrics(self.font()).horizontalAdvance(" ") * self._indent_size)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.blockCountChanged.connect(lambda _count: self._schedule_minimap_refresh())
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._refresh_internal_highlights)
        self.document().contentsChanged.connect(self._schedule_minimap_refresh)

        scrollbar = self.verticalScrollBar()
        scrollbar.valueChanged.connect(lambda _value: self._minimap_area.update())
        scrollbar.rangeChanged.connect(lambda _min, _max: self._minimap_area.update())

        self._update_line_number_area_width(0)
        self._refresh_internal_highlights()
        self._rebuild_minimap_density()

    def configure_syntax_highlighting(self, file_path: str | None, large_file_mode: bool) -> None:
        self._syntax_highlighter = build_highlighter(self.document(), file_path, large_file_mode)
        self._large_file_mode = large_file_mode
        if self._syntax_highlighter is None:
            self._language_id = LanguageId.PLAIN_TEXT
        else:
            self._language_id = self._syntax_highlighter.language_id
        self._language_display_name = LANGUAGE_DISPLAY_NAMES[self._language_id]
        self._schedule_minimap_refresh(immediate=True)

    def language_display_name(self) -> str:
        return self._language_display_name

    def language_id(self) -> LanguageId:
        return self._language_id

    def is_large_file_mode(self) -> bool:
        return self._large_file_mode

    def set_theme(self, theme_id: str | None) -> None:
        normalized_theme = normalize_theme_id(theme_id)
        if normalized_theme == self._theme_id:
            return
        self._theme_id = normalized_theme
        self._refresh_internal_highlights()
        self._line_number_area.update()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 8 + self.fontMetrics().horizontalAdvance("9") * digits

    def minimap_area_width(self) -> int:
        return self._minimap_width

    def line_number_area_paint_event(self, event) -> None:
        colors = self._active_theme_colors()
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(colors["line_number_bg"]))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(
                    QColor(colors["line_number_active_fg"]) if block_number == current_block
                    else QColor(colors["line_number_fg"])
                )
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(block_number + 1),
                )

            block = block.next()
            top = bottom
            if block.isValid():
                bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def minimap_area_paint_event(self, event) -> None:
        painter = QPainter(self._minimap_area)
        rect = event.rect()
        width = self._minimap_area.width()
        height = self._minimap_area.height()

        painter.fillRect(rect, QColor("#1f1f1f"))
        painter.setPen(QColor("#2d2d30"))
        painter.drawLine(0, 0, 0, height)

        if self._minimap_density:
            band_count = len(self._minimap_density)
            band_height = height / max(1, band_count)
            max_bar_width = max(6, width - 10)
            bar_color = QColor("#5f7488") if self._large_file_mode else QColor("#6f879c")

            for index, density in enumerate(self._minimap_density):
                if density <= 0.0:
                    continue

                y_start = int(index * band_height)
                y_end = int((index + 1) * band_height)
                draw_height = max(1, y_end - y_start)
                draw_width = max(2, int(max_bar_width * (0.2 + 0.8 * density)))
                x = width - draw_width - 4
                painter.fillRect(x, y_start, draw_width, draw_height, bar_color)

        self._paint_minimap_viewport(painter, width, height)
        if self._large_file_mode:
            painter.setPen(QColor("#f0c674"))
            painter.drawText(4, 14, "LFM")

    def handle_minimap_interaction(self, y_position: float, center: bool) -> None:
        area_height = max(1, self._minimap_area.height())
        ratio = min(max(y_position / area_height, 0.0), 1.0)
        scrollbar = self.verticalScrollBar()
        target = int(round(ratio * scrollbar.maximum()))
        if center:
            target -= scrollbar.pageStep() // 2
        target = max(scrollbar.minimum(), min(scrollbar.maximum(), target))
        scrollbar.setValue(target)

    def set_external_extra_selections(self, selections: list[QTextEdit.ExtraSelection]) -> None:
        self._external_extra_selections = list(selections)
        self._apply_extra_selections()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        content_rect = self.contentsRect()
        minimap_width = self.minimap_area_width()
        self._line_number_area.setGeometry(
            QRect(
                content_rect.left(),
                content_rect.top(),
                self.line_number_area_width(),
                content_rect.height(),
            )
        )
        self._minimap_area.setGeometry(
            QRect(
                content_rect.right() - minimap_width + 1,
                content_rect.top(),
                minimap_width,
                content_rect.height(),
            )
        )
        self._schedule_minimap_refresh()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API)
        modifiers = event.modifiers()
        if event.key() == Qt.Key.Key_Tab and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            self._indent_selection_or_insert_spaces()
            return

        if event.key() == Qt.Key.Key_Backtab:
            self._outdent_selection_or_line()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        ):
            self._insert_newline_with_auto_indent()
            return

        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt API)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()

            if delta != 0:
                self._adjust_zoom(1 if delta > 0 else -1)
            event.accept()
            return

        super().wheelEvent(event)

    def _update_line_number_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, self.minimap_area_width(), 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)
        self._minimap_area.update()

    def _schedule_minimap_refresh(self, immediate: bool = False) -> None:
        if immediate:
            self._minimap_refresh_timer.stop()
            self._rebuild_minimap_density()
            return

        interval_ms = self._minimap_large_refresh_ms if self._large_file_mode else self._minimap_normal_refresh_ms
        self._minimap_refresh_timer.start(interval_ms)

    def _rebuild_minimap_density(self) -> None:
        area_height = max(1, self._minimap_area.height())
        block_count = max(1, self.document().blockCount())
        if self._large_file_mode:
            band_count = min(140, area_height)
        else:
            band_count = min(260, area_height)
        band_count = max(24, band_count)

        densities: list[float] = []
        for index in range(band_count):
            if band_count == 1:
                block_index = 0
            else:
                block_index = int(round((index / (band_count - 1)) * (block_count - 1)))
            block = self.document().findBlockByNumber(block_index)
            text = block.text() if block.isValid() else ""
            densities.append(self._line_density(text))

        self._minimap_density = densities
        self._minimap_area.update()

    def _line_density(self, text: str) -> float:
        if not text:
            return 0.0

        if self._large_file_mode:
            return 1.0 if text.strip() else 0.0

        non_whitespace = sum(1 for char in text if not char.isspace())
        if non_whitespace <= 0:
            return 0.0
        return min(1.0, non_whitespace / 90.0)

    def _paint_minimap_viewport(self, painter: QPainter, width: int, height: int) -> None:
        scrollbar = self.verticalScrollBar()
        page_step = max(1, scrollbar.pageStep())
        scroll_total = max(1, scrollbar.maximum() + page_step)
        top_ratio = scrollbar.value() / scroll_total
        height_ratio = min(1.0, page_step / scroll_total)

        viewport_y = int(top_ratio * height)
        viewport_height = max(12, int(height * height_ratio))
        if viewport_y + viewport_height > height:
            viewport_y = max(0, height - viewport_height)

        painter.fillRect(2, viewport_y, width - 4, viewport_height, QColor(9, 71, 113, 90))
        painter.setPen(QColor("#4fa3df"))
        painter.drawRect(2, viewport_y, width - 5, max(1, viewport_height - 1))

    def _refresh_internal_highlights(self) -> None:
        self._internal_extra_selections = []
        self._add_current_line_highlight()
        self._add_bracket_highlights()
        self._apply_extra_selections()
        self._line_number_area.update()

    def _apply_extra_selections(self) -> None:
        super().setExtraSelections(self._internal_extra_selections + self._external_extra_selections)

    def _add_current_line_highlight(self) -> None:
        colors = self._active_theme_colors()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(colors["current_line_bg"]))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self._internal_extra_selections.append(selection)

    def _active_theme_colors(self) -> dict[str, str]:
        if self._theme_id == "light":
            return self._SLATE_LIGHT_THEME_COLORS
        return self._DEFAULT_THEME_COLORS

    def _add_bracket_highlights(self) -> None:
        cursor_pos = self.textCursor().position()
        candidates = (cursor_pos - 1, cursor_pos)

        for pos in candidates:
            char = self._character_at(pos)
            if not char:
                continue

            if char in self._OPENING_TO_CLOSING:
                match_pos = self._find_matching_bracket(pos, char, search_forward=True)
                self._append_bracket_selection(pos, is_matched=match_pos >= 0, is_primary=True)
                if match_pos >= 0:
                    self._append_bracket_selection(match_pos, is_matched=True, is_primary=False)
                return

            if char in self._CLOSING_TO_OPENING:
                match_pos = self._find_matching_bracket(pos, char, search_forward=False)
                self._append_bracket_selection(pos, is_matched=match_pos >= 0, is_primary=True)
                if match_pos >= 0:
                    self._append_bracket_selection(match_pos, is_matched=True, is_primary=False)
                return

    def _append_bracket_selection(self, pos: int, is_matched: bool, is_primary: bool) -> None:
        if pos < 0:
            return

        cursor = self.textCursor()
        cursor.setPosition(pos)
        cursor.movePosition(
            QTextCursor.MoveOperation.NextCharacter,
            QTextCursor.MoveMode.KeepAnchor,
            1,
        )

        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        if is_matched:
            selection.format.setBackground(QColor("#3a6ea5" if is_primary else "#2f4f78"))
            selection.format.setForeground(QColor("#ffffff"))
        else:
            selection.format.setBackground(QColor("#7a2f2f"))
            selection.format.setForeground(QColor("#ffffff"))
        self._internal_extra_selections.append(selection)

    def _find_matching_bracket(self, start_pos: int, bracket_char: str, search_forward: bool) -> int:
        char_count = max(0, self.document().characterCount() - 1)
        scanned = 0
        depth = 0

        if search_forward:
            opening = bracket_char
            closing = self._OPENING_TO_CLOSING[bracket_char]
            cursor = start_pos + 1
            while cursor < char_count and scanned < self._bracket_scan_limit:
                char = self._character_at(cursor)
                if char == opening:
                    depth += 1
                elif char == closing:
                    if depth == 0:
                        return cursor
                    depth -= 1
                cursor += 1
                scanned += 1
            return -1

        closing = bracket_char
        opening = self._CLOSING_TO_OPENING[bracket_char]
        cursor = start_pos - 1
        while cursor >= 0 and scanned < self._bracket_scan_limit:
            char = self._character_at(cursor)
            if char == closing:
                depth += 1
            elif char == opening:
                if depth == 0:
                    return cursor
                depth -= 1
            cursor -= 1
            scanned += 1
        return -1

    def _character_at(self, pos: int) -> str:
        if pos < 0:
            return ""

        char_count = max(0, self.document().characterCount() - 1)
        if pos >= char_count:
            return ""
        return self.document().characterAt(pos)

    def _indent_selection_or_insert_spaces(self) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            spaces_to_add = self._indent_size - (cursor.positionInBlock() % self._indent_size)
            cursor.insertText(" " * spaces_to_add)
            return

        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        first_block = self.document().findBlock(selection_start)
        last_block = self.document().findBlock(max(selection_start, selection_end - 1))

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        block = first_block
        while block.isValid():
            line_cursor = QTextCursor(block)
            line_cursor.insertText(self._indent_unit)
            if block.blockNumber() == last_block.blockNumber():
                break
            block = block.next()
        edit_cursor.endEditBlock()

    def _outdent_selection_or_line(self) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            self._remove_indent_from_block(cursor.block())
            return

        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        first_block = self.document().findBlock(selection_start)
        last_block = self.document().findBlock(max(selection_start, selection_end - 1))

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        block = first_block
        while block.isValid():
            self._remove_indent_from_block(block)
            if block.blockNumber() == last_block.blockNumber():
                break
            block = block.next()
        edit_cursor.endEditBlock()

    def _remove_indent_from_block(self, block) -> None:
        text = block.text()
        if not text:
            return

        remove_count = 0
        if text.startswith("\t"):
            remove_count = 1
        else:
            for char in text[: self._indent_size]:
                if char == " ":
                    remove_count += 1
                else:
                    break

        if remove_count <= 0:
            return

        line_cursor = QTextCursor(block)
        line_cursor.movePosition(
            QTextCursor.MoveOperation.NextCharacter,
            QTextCursor.MoveMode.KeepAnchor,
            remove_count,
        )
        line_cursor.removeSelectedText()

    def _insert_newline_with_auto_indent(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()

        line_prefix = cursor.block().text()[: cursor.positionInBlock()]
        leading_whitespace_size = len(line_prefix) - len(line_prefix.lstrip(" \t"))
        base_indent = line_prefix[:leading_whitespace_size]

        stripped_prefix = line_prefix.rstrip()
        extra_indent = ""
        if stripped_prefix.endswith(":") or stripped_prefix.endswith(("{", "[", "(")):
            extra_indent = self._indent_unit

        cursor.insertText("\n" + base_indent + extra_indent)

    def _adjust_zoom(self, step_direction: int) -> None:
        if step_direction == 0:
            return

        font = self.font()
        current_size = font.pointSizeF()
        if current_size <= 0:
            fallback_size = font.pointSize()
            current_size = float(fallback_size if fallback_size > 0 else 10.0)

        target_size = max(
            self._MIN_ZOOM_POINT_SIZE,
            min(self._MAX_ZOOM_POINT_SIZE, current_size + float(step_direction)),
        )
        if abs(target_size - current_size) < 1e-6:
            return

        font.setPointSizeF(target_size)
        self.setFont(font)
        self._line_number_area.setFont(font)
        self._sync_font_dependent_metrics()

    def _sync_font_dependent_metrics(self) -> None:
        self.setTabStopDistance(QFontMetrics(self.font()).horizontalAdvance(" ") * self._indent_size)
        self._update_line_number_area_width(0)
        self._line_number_area.update()
        self.viewport().update()
