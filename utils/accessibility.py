"""Gemeinsame Tastatur- und Accessibility-Hilfen für komplexe Dialoge."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLayout, QWidget


def _iter_layout_widgets(layout: QLayout | None) -> Iterator[QWidget]:
    """Liefert Widgets in der visuellen Layout-Reihenfolge, rekursiv."""

    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            yield widget
            yield from _iter_layout_widgets(widget.layout())
        elif child_layout is not None:
            yield from _iter_layout_widgets(child_layout)


def _is_focus_candidate(widget: QWidget, dialog: QDialog) -> bool:
    if widget is dialog:
        return False
    # ComboBox-Popups, Menüs und andere Kind-Fenster können über findChildren()
    # im Objektbaum auftauchen. QWidget.setTabOrder darf aber nur Widgets
    # desselben Top-Level-Fensters verbinden; sonst warnt Qt und die Kette wird
    # unzuverlässig.
    if widget.window() is not dialog:
        return False
    if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
        return False
    if not widget.isEnabled():
        return False
    # Explizit ausgeblendete Felder gehören nicht in die aktuelle Tab-Kette.
    # Widgets auf inaktiven Tabs werden von Qt später automatisch übersprungen.
    return not (widget.isHidden() and widget.parentWidget() is dialog)


def _focus_widgets(dialog: QDialog) -> list[QWidget]:
    ordered: list[QWidget] = []
    seen: set[int] = set()

    def add(widget: QWidget) -> None:
        marker = id(widget)
        if marker in seen or not _is_focus_candidate(widget, dialog):
            return
        seen.add(marker)
        ordered.append(widget)

    for widget in _iter_layout_widgets(dialog.layout()):
        add(widget)

    # Manche Qt-Container verwalten ihre Seiten intern statt im Dialog-Layout.
    # Diese Felder werden in stabiler Objekt-Erstellungsreihenfolge ergänzt.
    for widget in dialog.findChildren(QWidget):
        add(widget)

    return ordered


def _apply_dialog_tab_order(dialog: QDialog) -> None:
    try:
        widgets = _focus_widgets(dialog)
        for current, following in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(current, following)
        dialog.setProperty("budgetManagerTabOrderCount", len(widgets))
        dialog.setProperty("budgetManagerTabOrderConfigured", True)
    except RuntimeError:
        # Dialog wurde vor dem verzögerten Lauf bereits geschlossen/gelöscht.
        return


def configure_dialog_tab_order(dialog: QDialog) -> None:
    """Setzt eine deterministische Tab-Reihenfolge ohne Fokusdiebstahl.

    Der erste Lauf deckt normale Konstruktoren ab. Der verzögerte Lauf erfasst
    zusätzlich Felder, die während des Layout-Aufbaus oder über Seiten/Stacks
    erst am Ende des Ereigniszyklus vollständig registriert werden.
    """

    _apply_dialog_tab_order(dialog)
    QTimer.singleShot(0, lambda: _apply_dialog_tab_order(dialog))
