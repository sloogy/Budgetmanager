"""Das Suchfeld-plus-Dropdown der Schnelleingabe als eigenes Widget.

Getrennt von ``category_picker``: Dort steht die reine Auswahllogik, die
absichtlich fast ohne Qt auskommt und darum headless getestet werden kann
(siehe tests/test_category_combo_resolution.py). Ein QWidget dort haette
diese Eigenschaft zerstoert.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QComboBox, QLineEdit, QVBoxLayout, QWidget

from views.category_picker import (
    _clean_category_label,
    _same_text,
    filter_grouped_categories,
    populate_grouped_combo,
    resolve_combo_category,
)

logger = logging.getLogger("budgetmanager")


class CategorySearchPicker(QWidget):
    """Suchfeld plus gruppiertes Dropdown - die Auswahl aus der Schnelleingabe.

    Warum als Widget und nicht als Bauanleitung in jedem Dialog: Die Auswahl
    ist rund achtzig Zeilen Verhalten - live filtern, Popup oeffnen, nach der
    Auswahl die volle Liste wiederherstellen, den echten Namen aus Label und
    getipptem Text zurueckgewinnen. Die Schnelleingabe hatte das, der
    Zahlungsimport eine schlichte Auswahlliste; wer dort aus zweihundert
    Kategorien die richtige suchte, scrollte.

    Wer das Widget einsetzt, ruft ``set_rows`` mit den gruppierten Zeilen des
    Kategoriemodells auf und liest ``selected_category``. Der echte Name
    kommt aus ``resolve_combo_category`` - die aufrufende View validiert ihn
    danach weiterhin gegen das Modell, denn ein getippter Name muss nicht
    existieren.
    """

    #: Ausgeloest, wenn der Benutzer eine Kategorie im Dropdown bestaetigt.
    category_selected = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        such_platzhalter: str = "",
        such_hinweis: str = "",
        dropdown_hinweis: str = "",
        leer_hinweis: str = "",
    ) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, object]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.search = QLineEdit()
        if such_platzhalter:
            self.search.setPlaceholderText(such_platzhalter)
        if such_hinweis:
            self.search.setToolTip(such_hinweis)
        self.search.textEdited.connect(self._on_search_edited)
        layout.addWidget(self.search)

        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setMaxVisibleItems(18)
        if dropdown_hinweis:
            self.combo.setToolTip(dropdown_hinweis)
        if leer_hinweis:
            # setPlaceholderText gibt es erst ab Qt 6.0 und nicht auf jedem
            # Stil; ein fehlender Platzhalter ist kein Grund, den Dialog
            # scheitern zu lassen.
            try:
                self.combo.setPlaceholderText(leer_hinweis)
            except (AttributeError, TypeError) as fehler:
                logger.debug("Platzhalter im Kategorie-Dropdown: %s", fehler)
        self.combo.activated.connect(lambda _: self._on_combo_activated())
        layout.addWidget(self.combo)

    # ── Befuellen ────────────────────────────────────────────────────────
    def set_rows(
        self, rows: list[tuple[str, str, object]], *, bevorzugt: str = ""
    ) -> None:
        """Setzt die gruppierten Zeilen und waehlt ``bevorzugt`` vor, wenn moeglich."""
        self._rows = list(rows)
        self._rebuild(query="", preferred=bevorzugt)

    def set_category(self, kategorie: str) -> None:
        """Waehlt eine Kategorie und traegt sie ins Suchfeld ein."""
        self._rebuild(query="", preferred=kategorie)
        if kategorie:
            self.search.blockSignals(True)
            try:
                self.search.setText(_clean_category_label(kategorie) or kategorie)
            finally:
                self.search.blockSignals(False)

    # ── Lesen ────────────────────────────────────────────────────────────
    def selected_category(self) -> str:
        """Der echte Kategoriename - leer, wenn nichts Gueltiges gewaehlt ist."""
        if self.combo.currentIndex() < 0:
            return ""
        return resolve_combo_category(self.combo)

    def hat_auswahl(self) -> bool:
        return bool(self.selected_category())

    # ── Innenleben ───────────────────────────────────────────────────────
    def _rebuild(
        self, *, query: str = "", preferred: str = "", popup: bool = False
    ) -> None:
        gefiltert = filter_grouped_categories(self._rows, query)
        populate_grouped_combo(self.combo, gefiltert)

        gewaehlt = False
        wunsch = (preferred or "").strip()
        if wunsch:
            for i in range(self.combo.count()):
                if _same_text(self.combo.itemData(i), wunsch):
                    self.combo.setCurrentIndex(i)
                    gewaehlt = True
                    break

        if not gewaehlt:
            for i in range(self.combo.count()):
                data = self.combo.itemData(i)
                if isinstance(data, str) and data.strip():
                    self.combo.setCurrentIndex(i)
                    gewaehlt = True
                    break

        if not gewaehlt:
            self.combo.setCurrentIndex(-1)

        self.combo.setEnabled(gewaehlt)
        if popup and self.combo.count() > 0:
            QTimer.singleShot(0, self.combo.showPopup)

    def _on_search_edited(self, text: str) -> None:
        self._rebuild(query=text.strip(), popup=True)

    def _on_combo_activated(self) -> None:
        kategorie = self.selected_category()
        if not kategorie:
            return
        label = self.combo.currentText()
        self.search.blockSignals(True)
        try:
            self.search.setText(_clean_category_label(label) or kategorie)
        finally:
            self.search.blockSignals(False)
        # Nach der Auswahl wieder die volle Liste zeigen, die Auswahl behalten.
        self._rebuild(query="", preferred=kategorie)
        self.category_selected.emit(kategorie)
