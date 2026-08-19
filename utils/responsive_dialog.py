"""Zentrale DPI- und Kleinbildschirm-Härtung für Dialoge."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget


def fit_dialog_to_available_screen(widget: QWidget, *, margin: int = 32) -> None:
    """Begrenzt Minimum und aktuelle Größe auf die verfügbare Bildschirmfläche."""
    screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        return
    area = screen.availableGeometry()
    max_width = max(320, area.width() - margin)
    max_height = max(240, area.height() - margin)
    minimum = widget.minimumSize()
    widget.setMinimumSize(
        min(minimum.width(), max_width), min(minimum.height(), max_height)
    )
    size = widget.size()
    widget.resize(min(size.width(), max_width), min(size.height(), max_height))


def harden_dialog_for_screen(dialog: QDialog, *, margin: int = 32) -> None:
    """Wendet die Anpassung sofort und nochmals nach Abschluss des Layouts an."""
    fit_dialog_to_available_screen(dialog, margin=margin)
    QTimer.singleShot(0, lambda: fit_dialog_to_available_screen(dialog, margin=margin))
