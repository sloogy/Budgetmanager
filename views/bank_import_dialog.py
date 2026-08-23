"""Kanonischer Einstiegspunkt für den aktuellen Bankimport-Dialog.

Ergänzt den V3-Review-Import um sichere Mehrfachauswahl und konsistente
Massenbearbeitung. Die fachliche Import-/KI-Logik bleibt in V3/Model erhalten.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.twint_import_policy import TYP_TWINT_AI, is_twint_credit
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from views.bank_import_dialog_v3 import BankImportDialog as _BankImportDialogV3


class BankImportDialog(_BankImportDialogV3):
    """Aktiver Bankimport mit Strg-Auswahl und sicherer Massenbearbeitung."""

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._fix_intro_text()
        self._install_bulk_editor()
        self.chk_net_twint.setChecked(False)
        self.chk_net_twint.setToolTip(
            "TWINT-Verrechnung ist bewusst Opt-in: Treffer zuerst prüfen und "
            "erst danach die Verrechnung aktivieren."
        )

    def _fix_intro_text(self) -> None:
        """V3 leitet Tags aus Kategorien ab; der V2-Hinweis war veraltet."""
        for label in self.findChildren(QLabel):
            if label.text().startswith("Lokaler Review-Import:"):
                label.setText(
                    "Lokaler Review-Import: Typ und Kategorie können pro Zeile "
                    "geändert werden. Tags werden automatisch aus der gewählten "
                    "Kategorie übernommen. Mehrere Zeilen lassen sich mit "
                    "Strg+Mausklick oder Umschalt+Mausklick auswählen und gemeinsam "
                    "bearbeiten. Die KI lernt erst aus bestätigten Buchungen."
                )
                break

    def _install_bulk_editor(self) -> None:
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setToolTip(
            "Mehrere Zeilen: Strg+Mausklick; Bereich: Umschalt+Mausklick; "
            "alle Zeilen: Strg+A. Danach die Massenbearbeitung verwenden."
        )

        bulk = QHBoxLayout()
        bulk.addWidget(QLabel("Mehrfachauswahl:"))

        self.cmb_bulk_type = QComboBox()
        self.cmb_bulk_type.setToolTip("Typ für alle ausgewählten Zeilen setzen")
        self.cmb_bulk_type.addItem("Typ nicht ändern", "")
        self.cmb_bulk_type.addItem(TYP_EXPENSES, TYP_EXPENSES)
        self.cmb_bulk_type.addItem(TYP_INCOME, TYP_INCOME)
        self.cmb_bulk_type.addItem(TYP_TWINT_AI, TYP_TWINT_AI)
        bulk.addWidget(self.cmb_bulk_type)

        self.cmb_bulk_category = QComboBox()
        self.cmb_bulk_category.setToolTip(
            "Kategorie für kompatible ausgewählte Zeilen setzen"
        )
        self.cmb_bulk_category.addItem("Kategorie nicht ändern", "")
        for typ in (TYP_EXPENSES, TYP_INCOME):
            for name in self.categories.list_names(typ):
                self.cmb_bulk_category.addItem(
                    f"{typ} · {name}",
                    self._category_token(typ, name),
                )
        self.cmb_bulk_category.setMaxVisibleItems(24)
        bulk.addWidget(self.cmb_bulk_category, 1)

        self.cmb_bulk_use = QComboBox()
        self.cmb_bulk_use.setToolTip(
            "Übernahme/KI-Markierung für alle ausgewählten Zeilen setzen"
        )
        self.cmb_bulk_use.addItem("Auswahlstatus nicht ändern", "")
        self.cmb_bulk_use.addItem("Übernehmen / KI markieren", "checked")
        self.cmb_bulk_use.addItem("Nicht übernehmen", "unchecked")
        bulk.addWidget(self.cmb_bulk_use)

        self.btn_bulk_apply = QPushButton("Auf Auswahl anwenden")
        self.btn_bulk_apply.setToolTip(
            "Wendet die drei Dropdown-Einstellungen auf die markierten Zeilen an"
        )
        self.btn_bulk_apply.clicked.connect(self._apply_bulk_changes)
        bulk.addWidget(self.btn_bulk_apply)

        self.lbl_bulk_status = QLabel("")
        self.lbl_bulk_status.setMinimumWidth(170)
        bulk.addWidget(self.lbl_bulk_status)

        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertLayout(2, bulk)

    def _type_combo(self, typ: str, row: int) -> QComboBox:
        """Positive TWINT-Eingänge dürfen nie als Budgetbuchung angeboten werden."""
        use_item = self.table.item(row, self.COL_USE)
        if use_item is not None:
            try:
                tx_index = int(use_item.data(Qt.UserRole))
            except (TypeError, ValueError):
                tx_index = -1
            if 0 <= tx_index < len(self.transactions):
                if is_twint_credit(self.transactions[tx_index]):
                    combo = QComboBox()
                    combo.addItem(TYP_TWINT_AI, TYP_TWINT_AI)
                    combo.setToolTip(
                        "Positive TWINT-Eingänge sind nur KI-/Erstattungssignale "
                        "und werden nie als Einkommen oder Ausgabe gebucht."
                    )
                    combo.currentIndexChanged.connect(
                        lambda _index, current_row=row: self._type_changed(current_row)
                    )
                    return combo
        return super()._type_combo(typ, row)

    def _selected_rows(self) -> list[int]:
        selection = self.table.selectionModel()
        if selection is None:
            return []
        rows = {index.row() for index in selection.selectedRows()}
        if not rows:
            rows = {index.row() for index in self.table.selectedIndexes()}
        return sorted(rows)

    def _set_combo_data(self, combo: QComboBox, value: str) -> bool:
        index = combo.findData(value)
        if index < 0 or index == combo.currentIndex():
            return False
        combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)
        return True

    def _apply_bulk_changes(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(
                self,
                "Mehrfachauswahl",
                "Bitte zuerst Zeilen mit Strg+Mausklick, Umschalt+Mausklick "
                "oder Strg+A auswählen.",
            )
            return

        wanted_type = str(self.cmb_bulk_type.currentData() or "")
        category_token = str(self.cmb_bulk_category.currentData() or "")
        wanted_use = str(self.cmb_bulk_use.currentData() or "")
        if not any((wanted_type, category_token, wanted_use)):
            QMessageBox.information(
                self,
                "Massenbearbeitung",
                "In den Dropdowns wurde keine Änderung ausgewählt.",
            )
            return

        category_typ, category = self._decode_category_token(category_token)
        changed_rows: set[int] = set()
        skipped_policy = 0
        skipped_category = 0
        skipped_locked = 0

        self._updating_row = True
        try:
            for row in rows:
                use_item = self.table.item(row, self.COL_USE)
                if use_item is None:
                    continue
                try:
                    tx_index = int(use_item.data(Qt.UserRole))
                except (TypeError, ValueError):
                    continue

                if wanted_type:
                    if (
                        0 <= tx_index < len(self.transactions)
                        and is_twint_credit(self.transactions[tx_index])
                        and wanted_type != TYP_TWINT_AI
                    ):
                        skipped_policy += 1
                    else:
                        combo = self.table.cellWidget(row, self.COL_TYPE)
                        if isinstance(combo, QComboBox) and self._set_combo_data(
                            combo, wanted_type
                        ):
                            self._set_prediction_for_row(row, replace_tags=False)
                            changed_rows.add(row)

                if category:
                    current_type = self._row_type(row)
                    compatible = (
                        current_type == TYP_TWINT_AI or current_type == category_typ
                    )
                    if not compatible:
                        skipped_category += 1
                    else:
                        combo = self.table.cellWidget(row, self.COL_CATEGORY)
                        if isinstance(combo, QComboBox):
                            wanted_category_data = (
                                category_token
                                if current_type == TYP_TWINT_AI
                                else category
                            )
                            if self._set_combo_data(combo, wanted_category_data):
                                changed_rows.add(row)
                            self._sync_category_tags(row)

                if wanted_use:
                    if use_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        state = (
                            Qt.CheckState.Checked
                            if wanted_use == "checked"
                            else Qt.CheckState.Unchecked
                        )
                        if use_item.checkState() != state:
                            use_item.setCheckState(state)
                            changed_rows.add(row)
                    else:
                        skipped_locked += 1
        finally:
            self._updating_row = False

        self._refresh_effective_view()

        notes = [f"{len(changed_rows)} von {len(rows)} Zeilen geändert"]
        if skipped_policy:
            notes.append(f"{skipped_policy} TWINT durch Sicherheitsregel geschützt")
        if skipped_category:
            notes.append(f"{skipped_category} Kategorie nicht kompatibel")
        if skipped_locked:
            notes.append(f"{skipped_locked} gesperrte/duplizierte Zeilen")
        self.lbl_bulk_status.setText(" · ".join(notes))


__all__ = ["BankImportDialog"]
