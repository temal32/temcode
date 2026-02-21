from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ImageViewer(QWidget):
    _MIN_ZOOM_FACTOR = 0.1
    _MAX_ZOOM_FACTOR = 8.0
    _ZOOM_STEP = 1.2

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path = os.path.abspath(file_path)
        self._source_pixmap = QPixmap()
        self._zoom_factor = 1.0
        self._fit_to_window = True

        self.setObjectName("imageViewer")

        self._toolbar = QWidget(self)
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(6)

        self._zoom_out_button = QPushButton("-", self._toolbar)
        self._zoom_out_button.setToolTip("Zoom out (Ctrl+Mouse Wheel)")
        self._zoom_out_button.clicked.connect(self.zoom_out)

        self._zoom_in_button = QPushButton("+", self._toolbar)
        self._zoom_in_button.setToolTip("Zoom in (Ctrl+Mouse Wheel)")
        self._zoom_in_button.clicked.connect(self.zoom_in)

        self._actual_size_button = QPushButton("100%", self._toolbar)
        self._actual_size_button.setToolTip("Show actual pixel size")
        self._actual_size_button.clicked.connect(self.reset_zoom)

        self._fit_button = QPushButton("Fit", self._toolbar)
        self._fit_button.setCheckable(True)
        self._fit_button.setChecked(True)
        self._fit_button.setToolTip("Fit image to available area")
        self._fit_button.toggled.connect(self.set_fit_to_window)

        for button in (
            self._zoom_out_button,
            self._zoom_in_button,
            self._actual_size_button,
            self._fit_button,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._zoom_label = QLabel("Fit", self._toolbar)
        self._zoom_label.setObjectName("imageViewerZoomLabel")

        self._dimension_label = QLabel("", self._toolbar)
        self._dimension_label.setObjectName("imageViewerDimensions")
        self._dimension_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        toolbar_layout.addWidget(self._zoom_out_button, 0)
        toolbar_layout.addWidget(self._zoom_in_button, 0)
        toolbar_layout.addWidget(self._actual_size_button, 0)
        toolbar_layout.addWidget(self._fit_button, 0)
        toolbar_layout.addWidget(self._zoom_label, 0)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._dimension_label, 0)

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidget(self._image_label)
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar, 0)
        layout.addWidget(self._scroll_area, 1)

    def file_path(self) -> str:
        return self._file_path

    def has_image(self) -> bool:
        return not self._source_pixmap.isNull()

    def image_dimensions_text(self) -> str:
        if self._source_pixmap.isNull():
            return ""
        return f"{self._source_pixmap.width()} x {self._source_pixmap.height()} px"

    def set_image_path(self, file_path: str) -> bool:
        self._file_path = os.path.abspath(file_path)
        return self.reload_image()

    def reload_image(self) -> bool:
        pixmap = QPixmap(self._file_path)
        if pixmap.isNull():
            self._source_pixmap = QPixmap()
            self._image_label.clear()
            self._dimension_label.setText("Unavailable")
            self._zoom_label.setText("N/A")
            return False

        self._source_pixmap = pixmap
        self._dimension_label.setText(self.image_dimensions_text())
        self._render_pixmap()
        return True

    def set_fit_to_window(self, enabled: bool) -> None:
        self._fit_to_window = bool(enabled)
        self._fit_button.blockSignals(True)
        self._fit_button.setChecked(self._fit_to_window)
        self._fit_button.blockSignals(False)
        self._render_pixmap()

    def zoom_in(self) -> None:
        self._set_zoom_factor(self._zoom_factor * self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._set_zoom_factor(self._zoom_factor / self._ZOOM_STEP)

    def reset_zoom(self) -> None:
        self._set_zoom_factor(1.0)

    def eventFilter(self, watched: object, event: object) -> bool:  # noqa: N802 (Qt API)
        if watched is self._scroll_area.viewport() and isinstance(event, QWheelEvent):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        if self._fit_to_window and not self._source_pixmap.isNull():
            self._render_pixmap()

    def _set_zoom_factor(self, zoom_factor: float) -> None:
        clamped = max(self._MIN_ZOOM_FACTOR, min(self._MAX_ZOOM_FACTOR, zoom_factor))
        self._zoom_factor = clamped
        self._fit_to_window = False
        self._fit_button.blockSignals(True)
        self._fit_button.setChecked(False)
        self._fit_button.blockSignals(False)
        self._render_pixmap()

    def _render_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            self._image_label.clear()
            return

        if self._fit_to_window:
            viewport_size = self._scroll_area.viewport().size()
            if viewport_size.width() > 0 and viewport_size.height() > 0:
                scaled = self._source_pixmap.scaled(
                    viewport_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                scaled = self._source_pixmap
            self._zoom_label.setText("Fit")
        else:
            target_width = max(1, int(round(self._source_pixmap.width() * self._zoom_factor)))
            target_height = max(1, int(round(self._source_pixmap.height() * self._zoom_factor)))
            scaled = self._source_pixmap.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._zoom_label.setText(f"{int(round(self._zoom_factor * 100))}%")

        self._image_label.setPixmap(scaled)
        self._image_label.resize(scaled.size())
        self._image_label.adjustSize()
