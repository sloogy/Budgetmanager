"""Nicht-modale, barrierearme Rückmeldungen für normale Arbeitsabläufe.

Sicherheitsabfragen, irreversible Bestätigungen und echte Fehler bleiben bewusst
modale ``QMessageBox``-Dialoge. Reine Hinweise und korrigierbare Validierungs-
meldungen werden hierüber angezeigt, damit der Eingabefokus erhalten bleibt.
"""

from __future__ import annotations

import logging
from typing import Literal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

logger = logging.getLogger(__name__)

NotificationLevel = Literal["info", "warning"]


def _active_parent(parent: QWidget | None) -> QWidget | None:
    if parent is not None:
        return parent
    app = QApplication.instance()
    if app is None:
        return None
    active = app.activeWindow()
    return active if isinstance(active, QWidget) else None


def _announce_accessibly(widget: QWidget) -> None:
    """Best-effort Alert-Event für Orca/NVDA, kompatibel über Qt-Versionen."""

    try:
        from PySide6.QtGui import QAccessible, QAccessibleEvent

        event_type = getattr(getattr(QAccessible, "Event", QAccessible), "Alert")
        QAccessible.updateAccessibility(QAccessibleEvent(widget, event_type))
    except Exception:
        # Die sichtbare Meldung und AccessibleName/Description bleiben erhalten.
        logger.debug("QAccessible-Alert konnte nicht gesendet werden", exc_info=True)


def _status_bar_target(widget: QWidget) -> QMainWindow | None:
    current: QWidget | None = widget
    while current is not None:
        if isinstance(current, QMainWindow):
            return current
        current = current.parentWidget()
    top = widget.window()
    return top if isinstance(top, QMainWindow) else None


def _show_toast(
    parent: QWidget,
    title: str,
    message: str,
    *,
    level: NotificationLevel,
    timeout_ms: int,
) -> None:
    top = parent.window() if parent.window() is not None else parent
    old = getattr(top, "_budgetmanager_notification_toast", None)
    if isinstance(old, QLabel):
        old.hide()
        old.deleteLater()

    try:
        from utils.i18n import tr

        prefix = tr("msg.info") if level == "info" else tr("msg.warning")
    except Exception:
        prefix = str(title or message or " ").strip()
    visible_title = str(title or prefix).strip()
    visible_message = str(message or "").strip()
    text = f"{visible_title}\n{visible_message}" if visible_title else visible_message

    toast = QLabel(text, top)
    toast.setObjectName("budgetmanagerNotificationToast")
    toast.setWordWrap(True)
    toast.setTextInteractionFlags(Qt.TextSelectableByMouse)
    toast.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    toast.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    toast.setAccessibleName(visible_title or prefix)
    toast.setAccessibleDescription(visible_message)

    palette = top.palette()
    background_role = (
        QPalette.ColorRole.Highlight
        if level == "warning"
        else QPalette.ColorRole.Window
    )
    foreground_role = (
        QPalette.HighlightedText if level == "warning" else QPalette.WindowText
    )
    background = palette.color(background_role)
    foreground = palette.color(foreground_role)
    border = palette.color(QPalette.ColorRole.Mid)
    toast.setStyleSheet(
        "QLabel#budgetmanagerNotificationToast {"
        f"background-color: {background.name()};"
        f"color: {foreground.name()};"
        f"border: 1px solid {border.name()};"
        "border-radius: 8px;"
        "padding: 10px 14px;"
        "font-weight: 600;"
        "}"
    )

    available_width = max(280, top.width() - 40)
    toast.setMaximumWidth(min(600, available_width))
    toast.adjustSize()
    x = max(12, (top.width() - toast.width()) // 2)
    y = max(12, top.height() - toast.height() - 24)
    toast.move(x, y)
    toast.raise_()
    toast.show()
    setattr(top, "_budgetmanager_notification_toast", toast)
    _announce_accessibly(toast)

    timer = QTimer(toast)
    timer.setSingleShot(True)

    def _close() -> None:
        if getattr(top, "_budgetmanager_notification_toast", None) is toast:
            setattr(top, "_budgetmanager_notification_toast", None)
        toast.hide()
        toast.deleteLater()

    timer.timeout.connect(_close)
    timer.start(max(2500, timeout_ms))


def show_notification(
    parent: QWidget | None,
    title: str,
    message: str,
    *,
    level: NotificationLevel = "info",
    timeout_ms: int | None = None,
) -> None:
    """Zeigt eine nicht-modale Rückmeldung ohne Fokusverlust."""

    widget = _active_parent(parent)
    clean_title = str(title or "").strip()
    clean_message = str(message or "").strip()
    if not clean_message:
        clean_message = clean_title
        clean_title = ""

    if timeout_ms is None:
        timeout_ms = min(9000, max(4500, 3200 + len(clean_message) * 28))

    if widget is None:
        log = logger.warning if level == "warning" else logger.info
        log("%s: %s", clean_title, clean_message)
        return

    main_window = _status_bar_target(widget)
    if main_window is not None and widget.window() is main_window:
        status_text = (
            f"{clean_title}: {clean_message}" if clean_title else clean_message
        )
        main_window.statusBar().showMessage(status_text, timeout_ms)
        main_window.statusBar().setAccessibleName(clean_title or clean_message)
        main_window.statusBar().setAccessibleDescription(clean_message)
        _announce_accessibly(main_window.statusBar())
        return

    _show_toast(
        widget,
        clean_title,
        clean_message,
        level=level,
        timeout_ms=timeout_ms,
    )


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    """Nicht-modaler Ersatz für reine Informationsdialoge."""

    show_notification(parent, title, message, level="info")


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    """Nicht-modaler Hinweis für korrigierbare Eingabe-/Auswahlprobleme."""

    show_notification(parent, title, message, level="warning")
