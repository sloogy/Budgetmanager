"""Reusable cockpit layout widgets (v2.2.41).

``CollapsibleSection``
    Compact card with title, count, empty state and a drag handle that is only
    visible in the explicitly fixed layout mode.
``fit_table_height``
    Fits tables to their contents with a safe maximum height.
``ResponsiveColumns``
    Responsive one/two-column container with fixed-mode drag and drop.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

TWO_COLUMN_BREAKPOINT = 1180
MANUAL_TWO_COLUMN_BREAKPOINT = 720
ARROW_OPEN = "\u25be"  # ▾
ARROW_CLOSED = "\u25b8"  # ▸
DRAG_HANDLE = "\u2261"  # ≡ – plain glyph, no emoji font required
COCKPIT_MIME_TYPE = "application/x-budgetmanager-cockpit-section"


def _start_section_drag(source: QWidget, key: str) -> None:
    """Start a move drag for one cockpit section.

    The helper is shared by the small grip and the complete section header.
    Keeping the drag creation in one place avoids subtly different MIME or
    cursor behaviour between both entry points.
    """
    mime = QMimeData()
    mime.setData(COCKPIT_MIME_TYPE, QByteArray(key.encode("utf-8")))
    drag = QDrag(source)
    drag.setMimeData(mime)
    drag.exec(Qt.MoveAction)


class _SectionHeader(QWidget):
    """Draggable card header used in manual layout mode.

    Only the header is draggable, not the card body.  Buttons, tables and
    charts therefore keep their normal interaction while the large title area
    is much easier to grab than the former tiny ``≡`` button.
    """

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._press_pos: QPoint | None = None
        self._drag_enabled = False
        self.setObjectName("cockpitSectionHeader")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_drag_enabled(self, enabled: bool, *, tooltip: str = "") -> None:
        self._drag_enabled = bool(enabled)
        self.setCursor(Qt.OpenHandCursor if self._drag_enabled else Qt.ArrowCursor)
        self.setToolTip(tooltip if self._drag_enabled else "")
        self.setAccessibleName(tooltip or self._key)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._drag_enabled:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._drag_enabled or self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self.setCursor(Qt.ClosedHandCursor)
        try:
            _start_section_drag(self, self._key)
        finally:
            self.setCursor(Qt.OpenHandCursor)
            self._press_pos = None

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._press_pos = None
        super().mouseReleaseEvent(event)


class _SectionDragHandle(QToolButton):
    """Starts a move drag after the platform drag-distance threshold."""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._press_pos: QPoint | None = None
        self.setObjectName("cockpitSectionGrip")
        self.setText(DRAG_HANDLE)
        self.setAutoRaise(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self.isEnabled() or self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self.setCursor(Qt.ClosedHandCursor)
        try:
            _start_section_drag(self, self._key)
        finally:
            self.setCursor(Qt.OpenHandCursor)
            self._press_pos = None

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._press_pos = None
        super().mouseReleaseEvent(event)


class CollapsibleSection(QFrame):
    """Section with clickable header, count, compact empty state and drag handle."""

    toggled = Signal(str, bool)  # key, collapsed

    def __init__(self, key: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._collapsed = False
        self._empty = False
        self.setObjectName("cockpitSection")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        self.header = _SectionHeader(key, self)
        head = QHBoxLayout(self.header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)

        self.btn_drag = _SectionDragHandle(key, self.header)
        self.btn_drag.setVisible(False)
        head.addWidget(self.btn_drag)

        self.btn_toggle = QToolButton(self.header)
        self.btn_toggle.setObjectName("cockpitSectionToggle")
        self.btn_toggle.setText(ARROW_OPEN)
        self.btn_toggle.setAutoRaise(True)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(lambda: self.set_collapsed(not self._collapsed))
        head.addWidget(self.btn_toggle)

        self.lbl_title = QLabel(title, self.header)
        self.lbl_title.setObjectName("cockpitSectionTitle")
        self.lbl_title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        head.addWidget(self.lbl_title)

        self.lbl_count = QLabel("", self.header)
        self.lbl_count.setObjectName("cockpitSectionCount")
        self.lbl_count.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        head.addWidget(self.lbl_count)
        head.addStretch(1)
        outer.addWidget(self.header)

        self.lbl_empty = QLabel("", self)
        self.lbl_empty.setObjectName("cockpitSectionEmpty")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setVisible(False)
        outer.addWidget(self.lbl_empty)

        self.content = QWidget(self)
        self._content_layout = QVBoxLayout(self.content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        outer.addWidget(self.content)

    @property
    def key(self) -> str:
        return self._key

    def is_collapsed(self) -> bool:
        return self._collapsed

    def is_empty(self) -> bool:
        return self._empty

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def set_title(self, title: str) -> None:
        self.lbl_title.setText(title)

    def set_drag_enabled(self, enabled: bool, *, tooltip: str = "") -> None:
        """Show the handle only in fixed mode; normal content stays non-draggable."""
        self.btn_drag.setVisible(bool(enabled))
        self.btn_drag.setEnabled(bool(enabled))
        self.btn_drag.setToolTip(tooltip)
        self.btn_drag.setAccessibleName(tooltip or self.lbl_title.text())
        self.header.set_drag_enabled(bool(enabled), tooltip=tooltip)

    def set_collapsed(self, collapsed: bool, *, notify: bool = True) -> None:
        self._collapsed = bool(collapsed)
        self.btn_toggle.setText(ARROW_CLOSED if self._collapsed else ARROW_OPEN)
        self.content.setVisible(not self._collapsed and not self._empty)
        self.lbl_empty.setVisible(self._empty and not self._collapsed)
        if notify:
            self.toggled.emit(self._key, self._collapsed)

    def set_count(self, count: int | None) -> None:
        self.lbl_count.setText("" if count is None else f"({count})")

    def set_empty(self, empty: bool, hint: str = "") -> None:
        """Shrink an empty section instead of hiding it completely."""
        self._empty = bool(empty)
        if hint:
            self.lbl_empty.setText(hint)
        self.set_collapsed(self._collapsed, notify=False)


def fit_table_height(table, *, max_rows: int = 8, min_rows: int = 1) -> None:
    """Fit a table to its contents, capped at ``max_rows``."""
    try:
        rows = max(min_rows, min(table.rowCount(), max_rows))
        row_height = table.verticalHeader().defaultSectionSize() or 24
        header_height = table.horizontalHeader().height() or 26
        frame = 2 * table.frameWidth()
        table.setMinimumHeight(0)
        table.setFixedHeight(header_height + rows * row_height + frame + 4)
    except Exception:  # pragma: no cover - layout must never block startup
        pass


class ResponsiveColumns(QWidget):
    """Responsive cockpit canvas with independent columns and live drop preview.

    The previous implementation placed both columns in one shared ``QGridLayout``
    row model.  A tall tile on the left therefore forced the tile in the same
    row on the right down as well, creating large empty areas that could not be
    filled.  Each column now owns its own vertical layout (masonry-style), so a
    tile can move to the top of either column independently.
    """

    layout_changed = Signal(object, object)  # left keys, right keys

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(0)

        self._left_host = QWidget(self)
        self._left_host.setObjectName("cockpitColumnLeft")
        self._left_layout = QVBoxLayout(self._left_host)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_layout.setSpacing(12)

        self._right_host = QWidget(self)
        self._right_host.setObjectName("cockpitColumnRight")
        self._right_layout = QVBoxLayout(self._right_host)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(12)

        self._single_host = QWidget(self)
        self._single_host.setObjectName("cockpitColumnSingle")
        self._single_layout = QVBoxLayout(self._single_host)
        self._single_layout.setContentsMargins(0, 0, 0, 0)
        self._single_layout.setSpacing(12)

        self._placeholder = QFrame(self)
        self._placeholder.setObjectName("cockpitDropPlaceholder")
        self._placeholder.setMinimumHeight(58)
        placeholder_layout = QHBoxLayout(self._placeholder)
        placeholder_layout.setContentsMargins(12, 8, 12, 8)
        self._placeholder_label = QLabel("", self._placeholder)
        self._placeholder_label.setObjectName("cockpitDropPlaceholderText")
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setWordWrap(True)
        placeholder_layout.addWidget(self._placeholder_label)
        self._placeholder.hide()

        self._left: list[QWidget] = []
        self._right: list[QWidget] = []
        self._two_columns: bool | None = None
        self._drag_enabled = False
        self._drop_text = ""
        self._preview_column: str | None = None
        self._preview_index: int | None = None
        self._preview_source: QWidget | None = None
        self.setAcceptDrops(False)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QGridLayout) -> None:
        while layout.count():
            layout.takeAt(0)

    def add(self, widget: QWidget, *, column: str = "left") -> None:
        (self._left if column == "left" else self._right).append(widget)
        self._relayout(force=True)

    def set_columns(self, left: list[QWidget], right: list[QWidget]) -> None:
        self._left = list(left)
        self._right = list(right)
        self._clear_preview(repaint=False)
        self._relayout(force=True)

    def set_drag_enabled(
        self,
        enabled: bool,
        *,
        tooltip: str = "",
        drop_text: str = "",
    ) -> None:
        changed = self._drag_enabled != bool(enabled)
        self._drag_enabled = bool(enabled)
        self._drop_text = str(drop_text or tooltip or "")
        self._placeholder_label.setText(self._drop_text)
        self.setAcceptDrops(self._drag_enabled)
        # Manual mode deliberately keeps a real two-column canvas available.
        # The surrounding QScrollArea may scroll horizontally on very narrow
        # windows instead of merging the columns and hiding a valid drop target.
        self.setMinimumWidth(MANUAL_TWO_COLUMN_BREAKPOINT if self._drag_enabled else 0)
        for widget in self._left + self._right:
            setter = getattr(widget, "set_drag_enabled", None)
            if callable(setter):
                setter(self._drag_enabled, tooltip=tooltip)
        if not self._drag_enabled:
            self._clear_preview(repaint=False)
        if changed:
            self._relayout(force=True)

    def is_two_columns(self) -> bool:
        return bool(self._two_columns)

    @staticmethod
    def _key(widget: QWidget) -> str:
        value = getattr(widget, "key", "")
        return str(value() if callable(value) else value)

    def _widget_for_key(self, key: str) -> QWidget | None:
        for widget in self._left + self._right:
            if self._key(widget) == key:
                return widget
        return None

    def _column_for_point(self, point: QPoint, source: QWidget) -> str:
        if self._two_columns:
            right_start = self._right_host.geometry().left()
            return "left" if point.x() < right_start else "right"
        # Defensive fallback for programmatic/legacy one-column drags: adopt
        # the stored column of the card under the pointer. Manual mode itself
        # deliberately remains a real two-column canvas.
        for widget in self._left + self._right:
            if widget is source or not widget.isVisible():
                continue
            if widget.geometry().contains(point):
                return "left" if widget in self._left else "right"
        return "left" if source in self._left else "right"

    @staticmethod
    def _remove_widget(
        widget: QWidget, left: list[QWidget], right: list[QWidget]
    ) -> None:
        if widget in left:
            left.remove(widget)
        if widget in right:
            right.remove(widget)

    def _widget_top_in_canvas(self, widget: QWidget) -> int:
        return widget.mapTo(self, QPoint(0, 0)).y()

    def _insert_index(
        self,
        widgets: list[QWidget],
        point: QPoint,
        *,
        source: QWidget | None = None,
    ) -> int:
        visible = [
            widget for widget in widgets if widget is not source and widget.isVisible()
        ]
        for index, widget in enumerate(visible):
            center_y = self._widget_top_in_canvas(widget) + widget.height() // 2
            if point.y() < center_y:
                return index
        return len(visible)

    def _decode_source(self, event) -> QWidget | None:
        try:
            key = bytes(event.mimeData().data(COCKPIT_MIME_TYPE)).decode("utf-8")
        except Exception:
            return None
        return self._widget_for_key(key)

    def _show_preview(self, point: QPoint, source: QWidget) -> None:
        column = self._column_for_point(point, source)
        target = self._left if column == "left" else self._right
        index = self._insert_index(target, point, source=source)
        if (
            self._preview_column == column
            and self._preview_index == index
            and self._preview_source is source
        ):
            return
        self._preview_column = column
        self._preview_index = index
        self._preview_source = source
        self._relayout(force=True)

    def _clear_preview(self, *, repaint: bool = True) -> None:
        had_preview = self._preview_column is not None
        self._preview_column = None
        self._preview_index = None
        self._preview_source = None
        self._placeholder.hide()
        if repaint and had_preview:
            self._relayout(force=True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_enabled and event.mimeData().hasFormat(COCKPIT_MIME_TYPE):
            source = self._decode_source(event)
            if source is not None:
                self._show_preview(event.position().toPoint(), source)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_enabled and event.mimeData().hasFormat(COCKPIT_MIME_TYPE):
            source = self._decode_source(event)
            if source is not None:
                self._show_preview(event.position().toPoint(), source)
                event.acceptProposedAction()
                return
        self._clear_preview()
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._clear_preview()
        event.accept()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._drag_enabled or not event.mimeData().hasFormat(COCKPIT_MIME_TYPE):
            self._clear_preview()
            event.ignore()
            return
        source = self._decode_source(event)
        if source is None:
            self._clear_preview()
            event.ignore()
            return

        point = event.position().toPoint()
        target_column = self._preview_column or self._column_for_point(point, source)
        left, right = list(self._left), list(self._right)
        self._remove_widget(source, left, right)
        target = left if target_column == "left" else right
        target_index = self._preview_index
        if target_index is None:
            target_index = self._insert_index(target, point, source=source)
        target.insert(max(0, min(int(target_index), len(target))), source)
        self._left, self._right = left, right
        self._clear_preview(repaint=False)
        self._relayout(force=True)
        self.layout_changed.emit(
            [self._key(widget) for widget in self._left],
            [self._key(widget) for widget in self._right],
        )
        event.setDropAction(Qt.MoveAction)
        event.accept()

    def _fill_column(
        self,
        layout: QVBoxLayout,
        widgets: list[QWidget],
        *,
        column: str,
    ) -> None:
        source = self._preview_source
        display_widgets = [widget for widget in widgets if widget is not source]
        preview_index = self._preview_index if self._preview_column == column else None
        for index, widget in enumerate(display_widgets):
            if preview_index == index:
                layout.addWidget(self._placeholder)
                self._placeholder.show()
            layout.addWidget(widget)
        if preview_index is not None and preview_index >= len(display_widgets):
            layout.addWidget(self._placeholder)
            self._placeholder.show()
        # Independent stretches make both columns top-aligned without sharing
        # row heights. A tall left tile can no longer push right tiles down.
        layout.addStretch(1)

    def _relayout(self, *, force: bool = False) -> None:
        breakpoint = (
            MANUAL_TWO_COLUMN_BREAKPOINT
            if self._drag_enabled
            else TWO_COLUMN_BREAKPOINT
        )
        two = self._drag_enabled or self.width() >= breakpoint
        if not force and two == self._two_columns:
            return
        self._two_columns = two

        self._clear_layout(self._grid)
        self._clear_layout(self._left_layout)
        self._clear_layout(self._right_layout)
        self._clear_layout(self._single_layout)
        self._left_host.hide()
        self._right_host.hide()
        self._single_host.hide()
        self._placeholder.hide()

        if two:
            self._fill_column(self._left_layout, self._left, column="left")
            self._fill_column(self._right_layout, self._right, column="right")
            self._grid.addWidget(self._left_host, 0, 0, Qt.AlignTop)
            self._grid.addWidget(self._right_host, 0, 1, Qt.AlignTop)
            if self._drag_enabled:
                self._grid.setColumnStretch(0, 1)
                self._grid.setColumnStretch(1, 1)
            else:
                self._grid.setColumnStretch(0, 4)
                self._grid.setColumnStretch(1, 6)
            self._left_host.show()
            self._right_host.show()
        else:
            for widget in self._left + self._right:
                self._single_layout.addWidget(widget)
            self._single_layout.addStretch(1)
            self._grid.addWidget(self._single_host, 0, 0, Qt.AlignTop)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 0)
            self._single_host.show()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._relayout()
