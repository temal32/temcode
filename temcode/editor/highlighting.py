from __future__ import annotations

import builtins
import keyword
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from temcode.ui.style import DEFAULT_THEME_ID, normalize_theme_id


class LanguageId(str, Enum):
    PLAIN_TEXT = "plain_text"
    PYTHON = "python"
    HTML = "html"
    JAVASCRIPT = "javascript"
    JSON = "json"
    CSS = "css"
    MARKDOWN = "markdown"
    C_CPP = "c_cpp"


LANGUAGE_DISPLAY_NAMES: dict[LanguageId, str] = {
    LanguageId.PLAIN_TEXT: "Plain Text",
    LanguageId.PYTHON: "Python",
    LanguageId.HTML: "HTML",
    LanguageId.JAVASCRIPT: "JavaScript",
    LanguageId.JSON: "JSON",
    LanguageId.CSS: "CSS",
    LanguageId.MARKDOWN: "Markdown",
    LanguageId.C_CPP: "C/C++",
}


_SYNTAX_THEME_BASE: dict[str, str] = {
    "keyword": "#569cd6",
    "builtin": "#4ec9b0",
    "type": "#4ec9b0",
    "string": "#ce9178",
    "comment": "#6a9955",
    "number": "#b5cea8",
    "decorator": "#c586c0",
    "identifier": "#dcdcaa",
    "property": "#9cdcfe",
    "literal": "#4fc1ff",
    "operator": "#d4d4d4",
    "tag": "#569cd6",
    "attribute": "#9cdcfe",
    "entity": "#dcdcaa",
    "preprocessor": "#c586c0",
    "heading": "#4fc1ff",
    "emphasis": "#d7ba7d",
    "strong": "#dcdcaa",
    "code": "#ce9178",
    "link_text": "#9cdcfe",
    "link_url": "#4fc1ff",
    "quote": "#6a9955",
    "list_marker": "#c586c0",
    "hr": "#808080",
    "selector": "#d7ba7d",
    "at_rule": "#c586c0",
    "important": "#f44747",
    "punctuation": "#d4d4d4",
    "key": "#9cdcfe",
    "macro": "#c586c0",
}


_SYNTAX_THEME_OVERRIDES: dict[str, dict[str, str]] = {
    "light": {
        "keyword": "#0f4c81",
        "builtin": "#006a6a",
        "type": "#0b5fad",
        "string": "#a31515",
        "comment": "#2f7d32",
        "number": "#1f6feb",
        "decorator": "#7a3e9d",
        "identifier": "#6b4f00",
        "property": "#0b63b6",
        "literal": "#005f9e",
        "operator": "#334155",
        "tag": "#0f4c81",
        "attribute": "#2b5f8a",
        "entity": "#8b6f00",
        "preprocessor": "#7a3e9d",
        "heading": "#0f4c81",
        "emphasis": "#8b5a2b",
        "strong": "#5f370e",
        "code": "#a31515",
        "link_text": "#0b63b6",
        "link_url": "#0066cc",
        "quote": "#2f7d32",
        "list_marker": "#7a3e9d",
        "hr": "#94a3b8",
        "selector": "#0f4c81",
        "at_rule": "#7a3e9d",
        "important": "#b42318",
        "punctuation": "#475569",
        "key": "#0b63b6",
        "macro": "#7a3e9d",
    },
    "nord": {
        "keyword": "#81a1c1",
        "builtin": "#8fbcbb",
        "type": "#88c0d0",
        "string": "#a3be8c",
        "comment": "#616e88",
        "number": "#b48ead",
        "decorator": "#b48ead",
        "identifier": "#ebcb8b",
        "property": "#88c0d0",
        "literal": "#81a1c1",
        "operator": "#d8dee9",
        "tag": "#81a1c1",
        "attribute": "#8fbcbb",
        "entity": "#ebcb8b",
        "preprocessor": "#b48ead",
        "heading": "#88c0d0",
        "emphasis": "#d08770",
        "strong": "#ebcb8b",
        "code": "#a3be8c",
        "link_text": "#88c0d0",
        "link_url": "#81a1c1",
        "quote": "#616e88",
        "list_marker": "#b48ead",
        "hr": "#4c566a",
        "selector": "#ebcb8b",
        "at_rule": "#b48ead",
        "important": "#bf616a",
        "punctuation": "#d8dee9",
        "key": "#88c0d0",
        "macro": "#b48ead",
    },
    "forest": {
        "keyword": "#7fbf9f",
        "builtin": "#6ec9b1",
        "type": "#7dcf8c",
        "string": "#c8d88f",
        "comment": "#6f9d86",
        "number": "#c7a77a",
        "decorator": "#9fbf7f",
        "identifier": "#d8c794",
        "property": "#8fd8c4",
        "literal": "#7ac7c4",
        "operator": "#d7e2db",
        "tag": "#7fbf9f",
        "attribute": "#8fd8c4",
        "entity": "#d8c794",
        "preprocessor": "#9fbf7f",
        "heading": "#8fd8c4",
        "emphasis": "#c7a77a",
        "strong": "#d8c794",
        "code": "#c8d88f",
        "link_text": "#8fd8c4",
        "link_url": "#7ac7c4",
        "quote": "#6f9d86",
        "list_marker": "#9fbf7f",
        "hr": "#4b6659",
        "selector": "#d8c794",
        "at_rule": "#9fbf7f",
        "important": "#e07a5f",
        "punctuation": "#d7e2db",
        "key": "#8fd8c4",
        "macro": "#9fbf7f",
    },
    "colorful": {
        "keyword": "#4cc9f0",
        "builtin": "#2ec4b6",
        "type": "#00bbf9",
        "string": "#ffd6a5",
        "comment": "#9ef01a",
        "number": "#ffbe0b",
        "decorator": "#ff9f1c",
        "identifier": "#f2c3ff",
        "property": "#9bf6ff",
        "literal": "#00f5d4",
        "operator": "#f7f7ff",
        "tag": "#4cc9f0",
        "attribute": "#9bf6ff",
        "entity": "#ffd166",
        "preprocessor": "#ff9f1c",
        "heading": "#00bbf9",
        "emphasis": "#ffd166",
        "strong": "#fff3ff",
        "code": "#ffd6a5",
        "link_text": "#9bf6ff",
        "link_url": "#00bbf9",
        "quote": "#9ef01a",
        "list_marker": "#ff9f1c",
        "hr": "#8a6dff",
        "selector": "#ffd166",
        "at_rule": "#ff9f1c",
        "important": "#ff1744",
        "punctuation": "#f7f7ff",
        "key": "#9bf6ff",
        "macro": "#ff9f1c",
    },
}


def _syntax_theme_colors(theme_id: str | None) -> dict[str, str]:
    normalized = normalize_theme_id(theme_id)
    colors = dict(_SYNTAX_THEME_BASE)
    if normalized != DEFAULT_THEME_ID:
        colors.update(_SYNTAX_THEME_OVERRIDES.get(normalized, {}))
    return colors


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
    if extension in {".json", ".jsonc", ".geojson"}:
        return LanguageId.JSON
    if extension in {".css", ".scss", ".sass", ".less"}:
        return LanguageId.CSS
    if extension in {".md", ".markdown", ".mdown", ".mkd", ".mdx"}:
        return LanguageId.MARKDOWN
    if extension in {".c", ".h", ".hpp", ".hh", ".hxx", ".cpp", ".cc", ".cxx", ".ipp", ".ixx", ".inl"}:
        return LanguageId.C_CPP
    return LanguageId.PLAIN_TEXT


def build_highlighter(
    document: QTextDocument,
    file_path: str | None,
    large_file_mode: bool,
    theme_id: str | None = None,
) -> "TemcodeSyntaxHighlighter | None":
    language = detect_language(file_path)
    theme_colors = _syntax_theme_colors(theme_id)
    if language == LanguageId.PYTHON:
        return PythonSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.HTML:
        return HtmlSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.JAVASCRIPT:
        return JavaScriptSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.JSON:
        return JsonSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.CSS:
        return CssSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.MARKDOWN:
        return MarkdownSyntaxHighlighter(document, large_file_mode, theme_colors)
    if language == LanguageId.C_CPP:
        return CppSyntaxHighlighter(document, large_file_mode, theme_colors)
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

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document)
        self.large_file_mode = large_file_mode
        self._theme_colors = theme_colors

    def _token_format(self, token_name: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        foreground = self._theme_colors.get(token_name, self._theme_colors["keyword"])
        return _format(foreground=foreground, bold=bold, italic=italic)

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

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)

        self._keyword_format = self._token_format("keyword", bold=True)
        self._builtin_format = self._token_format("builtin")
        self._string_format = self._token_format("string")
        self._comment_format = self._token_format("comment", italic=True)
        self._number_format = self._token_format("number")
        self._decorator_format = self._token_format("decorator")
        self._identifier_format = self._token_format("identifier")

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

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)

        self._keyword_format = self._token_format("keyword", bold=True)
        self._literal_format = self._token_format("literal")
        self._builtin_format = self._token_format("builtin")
        self._string_format = self._token_format("string")
        self._comment_format = self._token_format("comment", italic=True)
        self._number_format = self._token_format("number")
        self._identifier_format = self._token_format("identifier")
        self._property_format = self._token_format("property")

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

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)

        self._tag_format = self._token_format("tag", bold=True)
        self._doctype_format = self._token_format("keyword", bold=True)
        self._attribute_format = self._token_format("attribute")
        self._operator_format = self._token_format("operator")
        self._string_format = self._token_format("string")
        self._comment_format = self._token_format("comment", italic=True)
        self._entity_format = self._token_format("entity")

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


class JsonSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.JSON

    _STATE_NONE = 0
    _STATE_BLOCK_COMMENT = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)
        self._key_format = self._token_format("key")
        self._string_format = self._token_format("string")
        self._comment_format = self._token_format("comment", italic=True)
        self._number_format = self._token_format("number")
        self._literal_format = self._token_format("literal", bold=True)
        self._punctuation_format = self._token_format("punctuation")

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"//[^\n]*"), self._comment_format),
            (QRegularExpression(r"/\*.*\*/"), self._comment_format),
            (QRegularExpression(r'"(?:[^"\\\n]|\\.)*"'), self._string_format),
            (QRegularExpression(r'"(?:[^"\\\n]|\\.)*"(?=\s*:)'), self._key_format),
            (
                QRegularExpression(
                    r"\b(?:0[xX][0-9A-Fa-f_]+|(?:\d[\d_]*\.\d[\d_]*|\.\d[\d_]+|\d[\d_]*)(?:[eE][+\-]?\d[\d_]*)?)\b"
                ),
                self._number_format,
            ),
            (QRegularExpression(r"\b(?:true|false|null)\b"), self._literal_format),
            (QRegularExpression(r"[{}\[\],:]"), self._punctuation_format),
        ]

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"//[^\n]*"), self._comment_format),
            (QRegularExpression(r'"[^"\n]*"'), self._string_format),
            (QRegularExpression(r'"[^"\n]*"(?=\s*:)'), self._key_format),
            (QRegularExpression(r"\b\d[\d_]*(?:\.\d[\d_]*)?\b"), self._number_format),
            (QRegularExpression(r"\b(?:true|false|null)\b"), self._literal_format),
            (QRegularExpression(r"[{}\[\],:]"), self._punctuation_format),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we skip multiline block comments to reduce updates.
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


class CssSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.CSS

    _STATE_NONE = 0
    _STATE_BLOCK_COMMENT = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)
        self._selector_format = self._token_format("selector")
        self._at_rule_format = self._token_format("at_rule", bold=True)
        self._property_format = self._token_format("attribute")
        self._string_format = self._token_format("string")
        self._comment_format = self._token_format("comment", italic=True)
        self._number_format = self._token_format("number")
        self._important_format = self._token_format("important", bold=True)
        self._punctuation_format = self._token_format("punctuation")

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"/\*.*\*/"), self._comment_format),
            (QRegularExpression(r"@[A-Za-z_-][A-Za-z0-9_-]*"), self._at_rule_format),
            (QRegularExpression(r"![iI]mportant\b"), self._important_format),
            (QRegularExpression(r'"(?:[^"\\\n]|\\.)*"'), self._string_format),
            (QRegularExpression(r"'(?:[^'\\\n]|\\.)*'"), self._string_format),
            (QRegularExpression(r"#[0-9A-Fa-f]{3,8}\b"), self._number_format),
            (
                QRegularExpression(
                    r"\b(?:\d[\d_]*(?:\.\d[\d_]*)?|\.\d[\d_]+)(?:%|px|em|rem|ch|ex|vh|vw|vmin|vmax|deg|rad|turn|s|ms|fr)?\b"
                ),
                self._number_format,
            ),
            (QRegularExpression(r"\b[A-Za-z-]+\b(?=\s*:)"), self._property_format),
            (QRegularExpression(r"(?<![A-Za-z0-9_-])[.#][A-Za-z_-][A-Za-z0-9_-]*"), self._selector_format),
            (QRegularExpression(r"::?[A-Za-z_-][A-Za-z0-9_-]*"), self._selector_format),
            (
                QRegularExpression(
                    r"(?<![A-Za-z0-9_-])[A-Za-z][A-Za-z0-9_-]*(?=\s*(?:[,{>+~]|$))"
                ),
                self._selector_format,
            ),
            (QRegularExpression(r"[{}:;(),>+~]"), self._punctuation_format),
        ]

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"/\*.*\*/"), self._comment_format),
            (QRegularExpression(r"@[A-Za-z_-][A-Za-z0-9_-]*"), self._at_rule_format),
            (QRegularExpression(r'"[^"\n]*"'), self._string_format),
            (QRegularExpression(r"'[^'\n]*'"), self._string_format),
            (QRegularExpression(r"\b[A-Za-z-]+\b(?=\s*:)"), self._property_format),
            (QRegularExpression(r"\b\d[\d_]*(?:\.\d[\d_]*)?\b"), self._number_format),
            (QRegularExpression(r"(?<![A-Za-z0-9_-])[.#][A-Za-z_-][A-Za-z0-9_-]*"), self._selector_format),
            (QRegularExpression(r"[{}:;(),>+~]"), self._punctuation_format),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we skip multiline block comments to reduce updates.
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


class MarkdownSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.MARKDOWN

    _STATE_NONE = 0
    _STATE_FENCED_CODE = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)
        self._heading_format = self._token_format("heading", bold=True)
        self._emphasis_format = self._token_format("emphasis", italic=True)
        self._strong_format = self._token_format("strong", bold=True)
        self._code_format = self._token_format("code")
        self._link_text_format = self._token_format("link_text")
        self._link_url_format = self._token_format("link_url")
        self._quote_format = self._token_format("quote", italic=True)
        self._list_marker_format = self._token_format("list_marker")
        self._hr_format = self._token_format("hr")

        self._fence_pattern = QRegularExpression(r"^\s*(?:```|~~~)")
        self._heading_pattern = QRegularExpression(r"^\s{0,3}#{1,6}\s+.*$")
        self._setext_pattern = QRegularExpression(r"^\s{0,3}(?:={3,}|-{3,})\s*$")
        self._quote_pattern = QRegularExpression(r"^\s{0,3}>.*$")
        self._list_pattern = QRegularExpression(r"^\s{0,3}(?:[-+*]|\d+\.)\s+")
        self._hr_pattern = QRegularExpression(r"^\s{0,3}(?:[-*_]\s*){3,}\s*$")

        if large_file_mode:
            self._inline_rules = self._build_simplified_inline_rules()
        else:
            self._inline_rules = self._build_full_inline_rules()

    def _build_full_inline_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"`[^`\n]+`"), self._code_format),
            (QRegularExpression(r"\*\*[^*\n]+\*\*|__[^_\n]+__"), self._strong_format),
            (QRegularExpression(r"\*[^*\n]+\*|_[^_\n]+_"), self._emphasis_format),
            (QRegularExpression(r"\[[^\]\n]+\](?=\()"), self._link_text_format),
            (QRegularExpression(r"\((?:https?://|\.{0,2}/|/)?[^)\s\n]+(?:\s+\"[^\"]*\")?\)"), self._link_url_format),
            (QRegularExpression(r"<https?://[^>\s]+>"), self._link_url_format),
        ]

    def _build_simplified_inline_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        return [
            (QRegularExpression(r"`[^`\n]+`"), self._code_format),
            (QRegularExpression(r"\[[^\]\n]+\](?=\()"), self._link_text_format),
            (QRegularExpression(r"\((?:https?://|\.{0,2}/|/)?[^)\s\n]+(?:\s+\"[^\"]*\")?\)"), self._link_url_format),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        is_fence_line = bool(self._fence_pattern.match(text).hasMatch())
        if self.previousBlockState() == self._STATE_FENCED_CODE:
            self.setFormat(0, len(text), self._code_format)
            if is_fence_line:
                self.setCurrentBlockState(self._STATE_NONE)
            else:
                self.setCurrentBlockState(self._STATE_FENCED_CODE)
            return

        if is_fence_line:
            self.setFormat(0, len(text), self._code_format)
            self.setCurrentBlockState(self._STATE_FENCED_CODE)
            return

        self.setCurrentBlockState(self._STATE_NONE)

        if self._heading_pattern.match(text).hasMatch() or self._setext_pattern.match(text).hasMatch():
            self.setFormat(0, len(text), self._heading_format)
            return

        if self._hr_pattern.match(text).hasMatch():
            self.setFormat(0, len(text), self._hr_format)
            return

        if self._quote_pattern.match(text).hasMatch():
            self.setFormat(0, len(text), self._quote_format)

        list_match = self._list_pattern.match(text)
        if list_match.hasMatch():
            self.setFormat(list_match.capturedStart(), list_match.capturedLength(), self._list_marker_format)

        self._apply_rules_to_text(text, self._inline_rules)


class CppSyntaxHighlighter(TemcodeSyntaxHighlighter):
    language_id = LanguageId.C_CPP

    _STATE_NONE = 0
    _STATE_BLOCK_COMMENT = 1

    def __init__(self, document: QTextDocument, large_file_mode: bool, theme_colors: dict[str, str]) -> None:
        super().__init__(document, large_file_mode, theme_colors)
        self._keyword_format = self._token_format("keyword", bold=True)
        self._type_format = self._token_format("type")
        self._preprocessor_format = self._token_format("preprocessor", bold=True)
        self._comment_format = self._token_format("comment", italic=True)
        self._string_format = self._token_format("string")
        self._number_format = self._token_format("number")
        self._identifier_format = self._token_format("identifier")
        self._macro_format = self._token_format("macro")

        if large_file_mode:
            self._rules = self._build_simplified_rules()
        else:
            self._rules = self._build_full_rules()

    def _build_full_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keywords = {
            "alignas",
            "alignof",
            "asm",
            "auto",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "consteval",
            "constexpr",
            "constinit",
            "continue",
            "co_await",
            "co_return",
            "co_yield",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "explicit",
            "export",
            "extern",
            "false",
            "for",
            "friend",
            "goto",
            "if",
            "inline",
            "mutable",
            "namespace",
            "new",
            "noexcept",
            "nullptr",
            "operator",
            "private",
            "protected",
            "public",
            "register",
            "reinterpret_cast",
            "return",
            "sizeof",
            "static",
            "static_assert",
            "struct",
            "switch",
            "template",
            "this",
            "thread_local",
            "throw",
            "true",
            "try",
            "typedef",
            "typename",
            "union",
            "using",
            "virtual",
            "volatile",
            "while",
        }
        for token in sorted(keywords):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))

        type_tokens = {
            "bool",
            "char",
            "char8_t",
            "char16_t",
            "char32_t",
            "double",
            "float",
            "int",
            "long",
            "short",
            "signed",
            "unsigned",
            "void",
            "wchar_t",
            "size_t",
            "ptrdiff_t",
            "std",
            "string",
            "vector",
            "map",
            "set",
            "array",
            "optional",
            "variant",
            "unique_ptr",
            "shared_ptr",
        }
        for token in sorted(type_tokens):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._type_format))

        rules.extend(
            [
                (QRegularExpression(r"^\s*#\s*[A-Za-z_]\w*.*$"), self._preprocessor_format),
                (QRegularExpression(r"\b[A-Z_][A-Z0-9_]{2,}\b"), self._macro_format),
                (QRegularExpression(r"//[^\n]*"), self._comment_format),
                (QRegularExpression(r"/\*.*\*/"), self._comment_format),
                (QRegularExpression(r'"(?:[^"\\\n]|\\.)*"'), self._string_format),
                (QRegularExpression(r"'(?:[^'\\\n]|\\.)*'"), self._string_format),
                (
                    QRegularExpression(
                        r"\b(?:0[xX][0-9A-Fa-f']+|0[bB][01']+|(?:\d[\d']*)(?:\.\d[\d']*)?(?:[eE][+\-]?\d[\d']*)?[fFlLuU]*)\b"
                    ),
                    self._number_format,
                ),
                (QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()"), self._identifier_format),
            ]
        )
        return rules

    def _build_simplified_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        simplified_keywords = {
            "if",
            "else",
            "for",
            "while",
            "switch",
            "case",
            "break",
            "continue",
            "return",
            "class",
            "struct",
            "enum",
            "namespace",
            "template",
            "typedef",
            "using",
            "const",
            "static",
            "virtual",
            "public",
            "private",
            "protected",
        }
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r"^\s*#\s*[A-Za-z_]\w*.*$"), self._preprocessor_format),
            (QRegularExpression(r"//[^\n]*"), self._comment_format),
            (QRegularExpression(r"/\*.*\*/"), self._comment_format),
            (QRegularExpression(r'"[^"\n]*"'), self._string_format),
            (QRegularExpression(r"'[^'\n]*'"), self._string_format),
            (QRegularExpression(r"\b\d[\d']*(?:\.\d[\d']*)?\b"), self._number_format),
        ]
        for token in sorted(simplified_keywords):
            rules.append((QRegularExpression(fr"\b{token}\b"), self._keyword_format))
        return rules

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        self.setCurrentBlockState(self._STATE_NONE)
        self._apply_rules_to_text(text, self._rules)

        # In large-file mode we skip multiline block comments to reduce updates.
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
