from __future__ import annotations

import builtins
import keyword
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument


class LanguageId(str, Enum):
    PLAIN_TEXT = "plain_text"
    PYTHON = "python"
    HTML = "html"
    JAVASCRIPT = "javascript"


LANGUAGE_DISPLAY_NAMES: dict[LanguageId, str] = {
    LanguageId.PLAIN_TEXT: "Plain Text",
    LanguageId.PYTHON: "Python",
    LanguageId.HTML: "HTML",
    LanguageId.JAVASCRIPT: "JavaScript",
}


def detect_language(file_path: str | None) -> LanguageId:
    if not file_path:
        return LanguageId.PLAIN_TEXT

    extension = Path(file_path).suffix.lower()
    if extension in {".py", ".pyw", ".pyi"}:
        return LanguageId.PYTHON
    if extension in {".html", ".htm", ".xhtml"}:
        return LanguageId.HTML
    if extension in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
        return LanguageId.JAVASCRIPT
    return LanguageId.PLAIN_TEXT


def build_highlighter(
    document: QTextDocument,
    file_path: str | None,
    large_file_mode: bool,
) -> "TemcodeSyntaxHighlighter | None":
    language = detect_language(file_path)
    if language == LanguageId.PYTHON:
        return PythonSyntaxHighlighter(document, large_file_mode)
    if language == LanguageId.HTML:
        return HtmlSyntaxHighlighter(document, large_file_mode)
    if language == LanguageId.JAVASCRIPT:
        return JavaScriptSyntaxHighlighter(document, large_file_mode)
    return None


def _format(*, foreground: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    text_format = QTextCharFormat()
    text_format.setForeground(QColor(foreground))
    text_format.setFontItalic(italic)
    if bold:
        text_format.setFontWeight(700)
    return text_format


class TemcodeSyntaxHighlighter(QSyntaxHighlighter):
    language_id: LanguageId = LanguageId.PLAIN_TEXT

    def __init__(self, document: QTextDocument, large_file_mode: bool) -> None:
        super().__init__(document)
        self.large_file_mode = large_file_mode

    def _apply_rules_to_text(
        self,
        text: str,
        rules: list[tuple[QRegularExpression, QTextCharFormat]],
        offset: int = 0,
    ) -> None:
        for pattern, text_format in rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(offset + match.capturedStart(), match.capturedLength(), text_format)


class PythonSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.PYTHON

    _STATE_NONE = 0
    _STATE_TRIPLE_SINGLE = 1
    _STATE_TRIPLE_DOUBLE = 2

    def __init__(self, document: QTextDocument, large_file_mode: bool) -> None:
        super().__init__(document, large_file_mode)

        self._keyword_format = _format(foreground="#569cd6", bold=True)
        self._builtin_format = _format(foreground="#4ec9b0")
        self._string_format = _format(foreground="#ce9178")
        self._comment_format = _format(foreground="#6a9955", italic=True)
        self._number_format = _format(foreground="#b5cea8")
        self._decorator_format = _format(foreground="#c586c0")
        self._identifier_format = _format(foreground="#dcdcaa")

        self._triple_single = QRegularExpression("'''")
        self._triple_double = QRegularExpression('"""')

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        for token in keyword.kwlist:
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))

        builtin_tokens = {
            name
            for name in dir(builtins)
            if not (name.startswith("__") and name.endswith("__"))
        }
        builtin_tokens.update({"self", "cls"})
        for token in sorted(builtin_tokens):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._builtin_format))

        rules.extend(
            [
                (QRegularExpression(r"#[^\n]*"), self._comment_format),
                (QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"), self._decorator_format),
                (
                    QRegularExpression(
                        r"\b(?:0[bB][01_]+|0[oO][0-7_]+|0[xX][0-9A-Fa-f_]+|(?:\d[\d_]*\.\d[\d_]*|\.\d[\d_]+|\d[\d_]*)(?:[eE][+\-]?\d[\d_]*)?)[jJ]?\b"
                    ),
                    self._number_format,
                ),
                (
                    QRegularExpression(
                        r"(?<![A-Za-z0-9_])(?:[rRuUbBfF]{0,2})(?:\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')"
                    ),
                    self._string_format,
                ),
                (QRegularExpression(r"(?<=\bdef\s)[A-Za-z_][A-Za-z0-9_]*"), self._identifier_format),
                (QRegularExpression(r"(?<=\bclass\s)[A-Za-z_][A-Za-z0-9_]*"), self._identifier_format),
            ]
        )
        return rules

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        simplified_keywords = {
            "def",
            "class",
            "import",
            "from",
            "return",
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "with",
            "async",
            "await",
            "pass",
        }
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r"#[^\n]*"), self._comment_format),
            (
                QRegularExpression(
                    r"(?<![A-Za-z0-9_])(?:[rRuUbBfF]{0,2})(?:\"[^\"\n]*\"|'[^'\n]*')"
                ),
                self._string_format,
            ),
            (QRegularExpression(r"\b\d[\d_]*(?:\.\d[\d_]*)?\b"), self._number_format),
            (QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"), self._decorator_format),
        ]
        for token in simplified_keywords:
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))
        return rules

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we avoid expensive multiline-state propagation.
        if self.large_file_mode:
            return

        in_triple_single = self._highlight_multiline(text, self._triple_single, self._STATE_TRIPLE_SINGLE)
        if not in_triple_single:
            self._highlight_multiline(text, self._triple_double, self._STATE_TRIPLE_DOUBLE)

    def _highlight_multiline(self, text: str, delimiter: QRegularExpression, state: int) -> bool:
        continuing_string = self.previousBlockState() == state
        if continuing_string:
            start_index = 0
        else:
            match = delimiter.match(text)
            start_index = match.capturedStart()

        first_match = True
        while start_index >= 0:
            string_start = start_index
            if not (continuing_string and first_match):
                string_start = self._expand_prefixed_delimiter_start(text, start_index)

            end_match = delimiter.match(text, start_index + 3)
            end_index = end_match.capturedStart()
            if end_index >= 0:
                string_end = end_index + 3
                self.setCurrentBlockState(self._STATE_NONE)
            else:
                self.setCurrentBlockState(state)
                string_end = len(text)

            self.setFormat(string_start, string_end - string_start, self._string_format)

            if end_index < 0:
                break

            next_match = delimiter.match(text, end_index + 3)
            start_index = next_match.capturedStart()
            first_match = False
            continuing_string = False

        return self.currentBlockState() == state

    def _expand_prefixed_delimiter_start(self, text: str, delimiter_start: int) -> int:
        prefix_start = delimiter_start
        cursor = delimiter_start - 1
        consumed = 0

        while cursor >= 0 and consumed < 2 and text[cursor] in "rRuUbBfF":
            prefix_start = cursor
            cursor -= 1
            consumed += 1

        if prefix_start != delimiter_start and cursor >= 0 and (text[cursor].isalnum() or text[cursor] == "_"):
            return delimiter_start
        return prefix_start


class JavaScriptSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.JAVASCRIPT

    _STATE_NONE = 0
    _STATE_BLOCK_COMMENT = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool) -> None:
        super().__init__(document, large_file_mode)

        self._keyword_format = _format(foreground="#569cd6", bold=True)
        self._literal_format = _format(foreground="#4fc1ff")
        self._builtin_format = _format(foreground="#4ec9b0")
        self._string_format = _format(foreground="#ce9178")
        self._comment_format = _format(foreground="#6a9955", italic=True)
        self._number_format = _format(foreground="#b5cea8")
        self._identifier_format = _format(foreground="#dcdcaa")
        self._property_format = _format(foreground="#9cdcfe")

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keywords = {
            "as",
            "async",
            "await",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "export",
            "extends",
            "finally",
            "for",
            "from",
            "function",
            "if",
            "implements",
            "import",
            "in",
            "instanceof",
            "interface",
            "let",
            "new",
            "package",
            "private",
            "protected",
            "public",
            "readonly",
            "return",
            "static",
            "super",
            "switch",
            "this",
            "throw",
            "try",
            "type",
            "typeof",
            "var",
            "void",
            "while",
            "with",
            "yield",
        }
        for token in sorted(keywords):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))

        literals = {"true", "false", "null", "undefined", "NaN", "Infinity"}
        for token in sorted(literals):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._literal_format))

        builtins = {
            "Array",
            "Boolean",
            "Date",
            "Error",
            "JSON",
            "Map",
            "Math",
            "Number",
            "Object",
            "Promise",
            "RegExp",
            "Set",
            "String",
            "Symbol",
            "BigInt",
            "console",
            "document",
            "window",
            "globalThis",
        }
        for token in sorted(builtins):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._builtin_format))

        rules.extend(
            [
                (QRegularExpression(r"//[^\n]*"), self._comment_format),
                (QRegularExpression(r"/\*.*\*/"), self._comment_format),
                (
                    QRegularExpression(
                        r"\b(?:0[xX][0-9A-Fa-f_]+n?|0[bB][01_]+n?|0[oO][0-7_]+n?|(?:\d[\d_]*\.\d[\d_]*|\.\d[\d_]+|\d[\d_]*)(?:[eE][+\-]?\d[\d_]*)?n?)\b"
                    ),
                    self._number_format,
                ),
                (QRegularExpression(r'"(?:[^"\\\n]|\\.)*"'), self._string_format),
                (QRegularExpression(r"'(?:[^'\\\n]|\\.)*'"), self._string_format),
                (QRegularExpression(r"`(?:[^`\\\n]|\\.)*`"), self._string_format),
                (QRegularExpression(r"(?<=\bfunction\s)[A-Za-z_$][A-Za-z0-9_$]*"), self._identifier_format),
                (QRegularExpression(r"(?<=\bclass\s)[A-Za-z_$][A-Za-z0-9_$]*"), self._identifier_format),
                (QRegularExpression(r"(?<=\binterface\s)[A-Za-z_$][A-Za-z0-9_$]*"), self._identifier_format),
                (QRegularExpression(r"(?<=\bnew\s)[A-Za-z_$][A-Za-z0-9_$]*"), self._identifier_format),
                (QRegularExpression(r"(?<=\.)[A-Za-z_$][A-Za-z0-9_$]*"), self._property_format),
            ]
        )
        return rules

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        simplified_keywords = {
            "const",
            "let",
            "var",
            "function",
            "class",
            "return",
            "if",
            "else",
            "for",
            "while",
            "switch",
            "case",
            "try",
            "catch",
            "finally",
            "import",
            "export",
        }
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r"//[^\n]*"), self._comment_format),
            (QRegularExpression(r'/\*[^*]*\*/'), self._comment_format),
            (QRegularExpression(r'"[^"\n]*"'), self._string_format),
            (QRegularExpression(r"'[^'\n]*'"), self._string_format),
            (QRegularExpression(r"`[^`\n]*`"), self._string_format),
            (QRegularExpression(r"\b\d[\d_]*(?:\.\d[\d_]*)?\b"), self._number_format),
        ]
        for token in sorted(simplified_keywords):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))
        return rules

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we skip multiline block comments to reduce rehighlight churn.
        if self.large_file_mode:
            return

        self._highlight_block_comments(text)

    def _highlight_block_comments(self, text: str) -> None:
        if self.previousBlockState() == self._STATE_BLOCK_COMMENT:
            start_index = 0
        else:
            start_index = text.find("/*")

        while start_index >= 0:
            end_index = text.find("*/", start_index + 2)
            if end_index >= 0:
                length = end_index - start_index + 2
                self.setCurrentBlockState(self._STATE_NONE)
            else:
                length = len(text) - start_index
                self.setCurrentBlockState(self._STATE_BLOCK_COMMENT)

            self.setFormat(start_index, length, self._comment_format)

            if end_index < 0:
                break
            start_index = text.find("/*", start_index + length)


class HtmlSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.HTML

    _STATE_NONE = 0
    _STATE_COMMENT = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool) -> None:
        super().__init__(document, large_file_mode)

        self._tag_format = _format(foreground="#569cd6", bold=True)
        self._doctype_format = _format(foreground="#569cd6", bold=True)
        self._attribute_format = _format(foreground="#9cdcfe")
        self._operator_format = _format(foreground="#d4d4d4")
        self._string_format = _format(foreground="#ce9178")
        self._comment_format = _format(foreground="#6a9955", italic=True)
        self._entity_format = _format(foreground="#dcdcaa")

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        doctype_pattern = QRegularExpression(r"<!DOCTYPE[^>]*>")
        doctype_pattern.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
        return [
            (doctype_pattern, self._doctype_format),
            (QRegularExpression(r"</?[A-Za-z][A-Za-z0-9:\-]*"), self._tag_format),
            (QRegularExpression(r"/?>"), self._tag_format),
            (QRegularExpression(r"\b[A-Za-z_:][A-Za-z0-9_:\-\.]*(?=\s*=)"), self._attribute_format),
            (QRegularExpression(r"="), self._operator_format),
            (QRegularExpression(r'"(?:[^"\\]|\\.)*"'), self._string_format),
            (QRegularExpression(r"'(?:[^'\\]|\\.)*'"), self._string_format),
            (QRegularExpression(r"=\s*[^\s\"'=<>`]+"), self._string_format),
            (QRegularExpression(r"&[A-Za-z0-9#]+;"), self._entity_format),
        ]

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"<!DOCTYPE[^>]*>"), self._doctype_format),
            (QRegularExpression(r"</?[A-Za-z][A-Za-z0-9:\-]*"), self._tag_format),
            (QRegularExpression(r"/?>"), self._tag_format),
            (QRegularExpression(r'"[^"\n]*"'), self._string_format),
            (QRegularExpression(r"'[^'\n]*'"), self._string_format),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we skip multiline comments to avoid broad rehighlight cascades.
        if self.large_file_mode:
            comment_match = QRegularExpression(r"<!--.*-->").globalMatch(text)
            while comment_match.hasNext():
                match = comment_match.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), self._comment_format)
            return

        self._highlight_html_comments(text)

    def _highlight_html_comments(self, text: str) -> None:
        if self.previousBlockState() == self._STATE_COMMENT:
            start_index = 0
        else:
            start_index = text.find("<!--")

        while start_index >= 0:
            end_index = text.find("-->", start_index + 4)
            if end_index >= 0:
                length = end_index - start_index + 3
                self.setCurrentBlockState(self._STATE_NONE)
            else:
                length = len(text) - start_index
                self.setCurrentBlockState(self._STATE_COMMENT)

            self.setFormat(start_index, length, self._comment_format)

            if end_index < 0:
                break
            start_index = text.find("<!--", start_index + length)
