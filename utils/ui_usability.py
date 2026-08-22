"""Zentrale UI-Härtung für Fokus, Accessibility und sichere Dialog-Defaults.

Die Regeln werden über einen QApplication-Eventfilter auf jedes neu angezeigte
Fenster angewendet. Dadurch profitieren auch selten geöffnete Dialoge, ohne dass
jede View eine eigene, leicht inkonsistente Umsetzung benötigt.

v2.2.22 (UI/ADHS-Audit):
- Destruktiv-Erkennung als Qt-freie Funktion ``is_destructive_text`` mit
  Wortgrenzen-Matching und vollständiger de/en/fr-Wortliste (vorher fehlten
  u.a. ``réinitialiser``/``retirer``/``clear``; Substring-Matching hätte
  harmlose Texte wie "Preset speichern" getroffen).
- Screenreader-Hinweis für Tabellen/Listen läuft über i18n (vorher
  hartkodiert deutsch – Bruch der de=en=fr-Regel).
- Einmal-Marker pro Widget und Popup-/Menü-Skip: der Show-Filter lief sonst
  bei JEDEM Öffnen (auch Combo-Dropdowns) erneut über den ganzen Widgetbaum.
- Fokus-Timer ist zerstörungssicher (Dialog kann zwischen Show und Timer
  bereits geschlossen/gelöscht sein).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_ENHANCED_PROP = "_bm_ui_enhanced"
_AUTO_NAME_PROP = "_bm_ui_auto_accessible_name"
_AUTO_DESC_PROP = "_bm_ui_auto_accessible_description"

# Wortliste je Sprache; Matching erfolgt auf WORT-Ebene (siehe
# ``is_destructive_text``), damit z.B. "Preset" nicht über das enthaltene
# "reset" faelschlich als destruktiv gilt.
# Destruktiv-Erkennung: Qt-frei in utils/ui_text_rules.py (auditierbar ohne
# PySide6); hier nur re-exportiert.
from utils.ui_text_rules import (
    clean_ui_text as _clean,
)
from utils.ui_text_rules import (
    is_destructive_text,
)


def _itemview_hint() -> str:
    """Screenreader-Hinweis für Tabellen/Listen – lokalisiert.

    Lazy-Import, damit dieses Modul auch ohne geladene i18n nutzbar bleibt;
    der englische Fallback greift nur, wenn tr() selbst nicht verfügbar ist.
    """
    try:
        from utils.i18n import tr

        return tr("a11y.itemview_hint")
    except Exception:  # pragma: no cover - defensiver Fallback
        return "Table or list. Navigate with arrow keys, Enter opens the selection."


def _associated_form_label(widget: QWidget) -> str:
    """Findet das sichtbare Formularlabel eines Eingabefelds.

    Qt setzt bei verschachtelten Layouts die Widgets häufig direkt auf den
    Dialog als Parent. Deshalb reicht ``parent.layout().indexOf(widget)`` nicht:
    die eigentliche Feldzeile kann mehrere Layout-Ebenen tiefer liegen.
    """

    def from_layout(layout, target: QWidget) -> str:
        if layout is None:
            return ""
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(target)
            if isinstance(label, QLabel):
                cleaned = _clean(label.text())
                if cleaned:
                    return cleaned
        if isinstance(layout, QHBoxLayout):
            index = layout.indexOf(target)
            for previous in range(index - 1, -1, -1):
                item = layout.itemAt(previous)
                label = item.widget() if item is not None else None
                if isinstance(label, QLabel):
                    cleaned = _clean(label.text())
                    if cleaned:
                        return cleaned
                if label is not None:
                    break
        if isinstance(layout, QVBoxLayout):
            index = layout.indexOf(target)
            if index > 0:
                item = layout.itemAt(index - 1)
                label = item.widget() if item is not None else None
                if isinstance(label, QLabel):
                    cleaned = _clean(label.text())
                    if cleaned:
                        return cleaned
        if isinstance(layout, QGridLayout):
            index = layout.indexOf(target)
            if index >= 0:
                row, column, _row_span, _column_span = layout.getItemPosition(index)
                for previous_column in range(column - 1, -1, -1):
                    item = layout.itemAtPosition(row, previous_column)
                    label = item.widget() if item is not None else None
                    if isinstance(label, QLabel):
                        cleaned = _clean(label.text())
                        if cleaned:
                            return cleaned
                    if label is not None:
                        break
        for index in range(layout.count()):
            item = layout.itemAt(index)
            child_layout = item.layout() if item is not None else None
            if child_layout is not None:
                label = from_layout(child_layout, target)
                if label:
                    return label
        return ""

    target: QWidget | None = widget
    parent = widget.parentWidget()
    while parent is not None and target is not None:
        label = from_layout(parent.layout(), target)
        if label:
            return label
        # Explizite Buddy-Verknüpfungen haben Vorrang, falls eine View sie setzt.
        for child in parent.children():
            if isinstance(child, QLabel) and child.buddy() is widget:
                cleaned = _clean(child.text())
                if cleaned:
                    return cleaned
        target = parent
        parent = parent.parentWidget()
    return ""


def _widget_label(widget: QWidget) -> str:
    """Ermittelt einen verständlichen, möglichst sichtbaren Namen."""
    candidates: list[str] = []
    if isinstance(widget, QAbstractButton):
        candidates.append(widget.text())
    associated = _associated_form_label(widget)
    if associated:
        candidates.append(associated)
    if isinstance(widget, QComboBox):
        candidates.append(widget.placeholderText())
    if isinstance(widget, QLineEdit):
        candidates.append(widget.placeholderText())
    candidates.extend(
        [widget.toolTip(), widget.statusTip(), widget.whatsThis(), widget.objectName()]
    )
    for candidate in candidates:
        cleaned = _clean(candidate)
        if cleaned:
            return cleaned
    return widget.metaObject().className()


def _is_destructive(button: QAbstractButton) -> bool:
    """Erkennt auch Icon-only-Aktionen über Tooltip/A11y-Metadaten."""
    return any(
        is_destructive_text(candidate)
        for candidate in (
            button.text(),
            button.toolTip(),
            button.accessibleName(),
            button.whatsThis(),
        )
        if _clean(candidate)
    )


def _editable_widgets(root: QWidget) -> Iterable[QWidget]:
    types = (
        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
        QDateEdit,
        QDateTimeEdit,
        QTextEdit,
        QPlainTextEdit,
    )
    for child in root.findChildren(QWidget):
        if isinstance(child, types) and child.isEnabled() and child.focusPolicy() != 0:
            yield child


def _is_transient_window(widget: QWidget) -> bool:
    """Popups, Menüs und Tooltips überspringen – sie sind kurzlebig und der
    Baum-Scan bei jedem Öffnen (z.B. Combo-Dropdown) wäre reiner Overhead."""
    if isinstance(widget, QMenu):
        return True
    flags = widget.windowFlags()
    for transient in (Qt.Popup, Qt.ToolTip, Qt.SplashScreen):
        if (flags & Qt.WindowType_Mask) == transient:
            return True
    return False


def _localize_dialog_button_box(box: QDialogButtonBox) -> None:
    """Übersetzt Qt-Standardbuttons mit der aktiven App-Sprache.

    Ohne installierten Qt-Systemübersetzer erscheinen Standardbuttons auf
    manchen Plattformen englisch (z. B. ``Close``/``Cancel``), obwohl der Rest
    der Oberfläche Deutsch oder Französisch ist.
    """
    try:
        from utils.i18n import tr

        mapping = {
            QDialogButtonBox.Ok: "btn.ok",
            QDialogButtonBox.Save: "btn.save",
            QDialogButtonBox.Cancel: "btn.cancel",
            QDialogButtonBox.Close: "btn.close",
            QDialogButtonBox.Apply: "btn.apply",
            QDialogButtonBox.Yes: "btn.yes",
            QDialogButtonBox.No: "btn.no",
            QDialogButtonBox.Open: "btn.open",
        }
        for standard, key in mapping.items():
            button = box.button(standard)
            if button is not None:
                button.setText(tr(key))
    except Exception:
        logger.debug(
            "Qt-Standardbuttons konnten nicht lokalisiert werden", exc_info=True
        )


def enhance_widget_tree(root: QWidget) -> None:
    """Ergänzt fehlende zugängliche Namen/Beschreibungen und sichere Defaults.

    Idempotent: bereits gehärtete Widgets tragen einen Marker
    (``_bm_ui_enhanced``) und werden übersprungen – wiederholte Show-Events
    (Minimieren/Restore, Kind-Dialoge) kosten damit praktisch nichts mehr.
    """
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        try:
            if widget.property(_ENHANCED_PROP):
                continue
            widget.setProperty(_ENHANCED_PROP, True)

            if not _clean(widget.accessibleName()):
                widget.setAccessibleName(_widget_label(widget))
                widget.setProperty(_AUTO_NAME_PROP, True)
            if not _clean(widget.accessibleDescription()) and _clean(widget.toolTip()):
                widget.setAccessibleDescription(_clean(widget.toolTip()))
                widget.setProperty(_AUTO_DESC_PROP, True)

            if isinstance(widget, QDialogButtonBox):
                _localize_dialog_button_box(widget)

            if isinstance(widget, QAbstractItemView) and not _clean(
                widget.accessibleDescription()
            ):
                widget.setAccessibleDescription(_itemview_hint())
                widget.setProperty(_AUTO_DESC_PROP, True)

            if isinstance(widget, QAbstractButton) and _is_destructive(widget):
                # Destruktive Aktionen dürfen nie unabsichtlich durch Enter
                # ausgelöst werden.
                try:
                    widget.setAutoDefault(False)
                    widget.setDefault(False)
                except AttributeError:
                    pass
        except RuntimeError:
            continue

    if isinstance(root, QDialog):
        # In DialogButtonBoxen ist Abbrechen immer klar erreichbar; destruktive
        # Buttons werden nicht zum Default. Bestehende explizite
        # Speichern-Defaults bleiben unangetastet.
        for box in root.findChildren(QDialogButtonBox):
            for button in box.buttons():
                if _is_destructive(button):
                    button.setAutoDefault(False)
                    button.setDefault(False)


def focus_first_input(dialog: QDialog) -> None:
    """Setzt beim Öffnen den Fokus auf das erste sinnvolle Eingabefeld.

    Nur wenn der Dialog selbst oder kein Kind den Fokus besitzt. Explizit von
    der View gesetzte Foki werden dadurch nicht überschrieben. Der Aufruf ist
    zerstörungssicher: zwischen Show-Event und Timer kann der Dialog bereits
    geschlossen und das C++-Objekt gelöscht sein (RuntimeError-Guard).
    """
    try:
        if not dialog.isVisible():
            return
        current = dialog.focusWidget()
        if current is not None and current is not dialog:
            return
        for widget in _editable_widgets(dialog):
            if widget.isVisibleTo(dialog):
                widget.setFocus()
                if isinstance(widget, QLineEdit):
                    # Vorbefüllte Werte niemals global markieren: Ein einzelner
                    # Tastendruck könnte sonst den kompletten Inhalt ersetzen.
                    widget.setCursorPosition(len(widget.text()))
                return
    except RuntimeError:
        # Qt-Objekt wurde zwischenzeitlich zerstört – nichts zu tun.
        return


def refresh_accessibility(root: QWidget) -> None:
    """Erzeugt nur automatisch gesetzte A11y-Texte neu.

    Explizite ``setAccessibleName``-Werte einer View bleiben unangetastet. Die
    Funktion ist für dynamische Beschriftungen und echte Qt-LanguageChange-
    Ereignisse gedacht.
    """
    for widget in [root, *root.findChildren(QWidget)]:
        try:
            if bool(widget.property(_AUTO_NAME_PROP)):
                widget.setAccessibleName("")
                widget.setProperty(_AUTO_NAME_PROP, False)
            if bool(widget.property(_AUTO_DESC_PROP)):
                widget.setAccessibleDescription("")
                widget.setProperty(_AUTO_DESC_PROP, False)
            widget.setProperty(_ENHANCED_PROP, False)
        except RuntimeError:
            continue
    enhance_widget_tree(root)


class UiUsabilityFilter(QObject):
    """Wendet UI-Regeln auf jedes sichtbar werdende Top-Level-Widget an."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Show and isinstance(watched, QWidget):
            try:
                if _is_transient_window(watched):
                    return False
                enhance_widget_tree(watched)
                if isinstance(watched, QDialog):
                    QTimer.singleShot(0, lambda w=watched: focus_first_input(w))
            except Exception:
                logger.debug("UI-Usability-Härtung fehlgeschlagen", exc_info=True)
        elif event.type() == QEvent.LanguageChange and isinstance(watched, QWidget):
            try:
                if not _is_transient_window(watched):
                    refresh_accessibility(watched)
            except Exception:
                logger.debug("Accessibility-Neuaufbau fehlgeschlagen", exc_info=True)
        return False


def install_ui_usability(app) -> UiUsabilityFilter:
    """Installiert den globalen Filter (idempotent) und gibt ihn zurück."""
    existing = app.property("budgetmanagerUiUsabilityFilter")
    if isinstance(existing, UiUsabilityFilter):
        return existing
    filt = UiUsabilityFilter(app)
    app.installEventFilter(filt)
    app.setProperty("budgetmanagerUiUsabilityFilter", filt)
    return filt
