"""Kanonischer Einstiegspunkt für den aktuellen Bankimport-Dialog.

Ergänzt den V3-Review-Import um sichere Mehrfachauswahl, Dropdown-
Massenbearbeitung und eine checkbare Tag-Auswahl. Kategorie-Tags bleiben
verbindlich; zusätzliche vorhandene Tags können bewusst ergänzt werden.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.twint_import_policy import TYP_TWINT_AI, is_twint_credit
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from views.bank_import_dialog_v3 import BankImportDialog as _BankImportDialogV3


class CheckableTagCombo(QComboBox):
    """Dropdown mit Checkboxen für bekannte Tags.

    Kategorie-Tags werden als gesperrte Pflicht-Tags angezeigt. Zusätzliche
    Tags sind frei an-/abwählbar, ohne dass freie Texte oder unbekannte Tags
    in den Import gelangen können.
    """

    tagsChanged = Signal()
    _LOCK_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    _NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(
        self,
        tag_names: tuple[str, ...],
        *,
        selected: tuple[str, ...] = (),
        locked: tuple[str, ...] = (),
        parent=None,
    ):
        super().__init__(parent)
        self.setEditable(True)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)
            line_edit.setPlaceholderText("Tags wählen…")
        self.setMaxVisibleItems(24)
        self.view().pressed.connect(self._toggle_index)
        self._rebuild(tag_names, selected=selected, locked=locked)
        self.currentIndexChanged.connect(lambda _index: self._refresh_text())

    @staticmethod
    def _key(value: str) -> str:
        return str(value or "").casefold()

    def _rebuild(
        self,
        tag_names: tuple[str, ...],
        *,
        selected: tuple[str, ...],
        locked: tuple[str, ...],
    ) -> None:
        selected_keys = {self._key(name) for name in selected}
        locked_keys = {self._key(name) for name in locked}
        self.clear()
        model = self.model()
        for name in tag_names:
            item = QStandardItem(name)
            item.setCheckable(True)
            item.setData(name, self._NAME_ROLE)
            is_locked = self._key(name) in locked_keys
            item.setData(is_locked, self._LOCK_ROLE)
            if is_locked:
                item.setText(f"🔒 {name}")
                item.setToolTip("Pflicht-Tag der gewählten Kategorie")
            item.setCheckState(
                Qt.CheckState.Checked
                if is_locked or self._key(name) in selected_keys
                else Qt.CheckState.Unchecked
            )
            model.appendRow(item)
        self._refresh_text()

    def _toggle_index(self, index) -> None:
        item = self.model().itemFromIndex(index)
        if item is None or bool(item.data(self._LOCK_ROLE)):
            return
        item.setCheckState(
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._refresh_text()
        self.tagsChanged.emit()

    def _refresh_text(self) -> None:
        names = self.selected_tags()
        text = ", ".join(names)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setText(text)
        self.setToolTip(text or "Keine Tags gewählt")

    def selected_tags(self) -> tuple[str, ...]:
        names: list[str] = []
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            name = str(item.data(self._NAME_ROLE) or "")
            if name:
                names.append(name)
        return tuple(names)

    def locked_tags(self) -> tuple[str, ...]:
        names: list[str] = []
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None or not bool(item.data(self._LOCK_ROLE)):
                continue
            name = str(item.data(self._NAME_ROLE) or "")
            if name:
                names.append(name)
        return tuple(names)

    def set_locked_tags(self, locked: tuple[str, ...]) -> None:
        """Wechselt Pflicht-Tags, ohne alte Kategorie-Tags mitzuschleppen."""
        previous_locked = {self._key(name) for name in self.locked_tags()}
        selected_optional = tuple(
            name
            for name in self.selected_tags()
            if self._key(name) not in previous_locked
        )
        catalog = tuple(
            str(self.model().item(row).data(self._NAME_ROLE) or "")
            for row in range(self.model().rowCount())
            if self.model().item(row) is not None
        )
        self._rebuild(catalog, selected=selected_optional, locked=locked)

    def set_tag_checked(self, name: str, checked: bool) -> bool:
        wanted = self._key(name)
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None or self._key(item.data(self._NAME_ROLE)) != wanted:
                continue
            if bool(item.data(self._LOCK_ROLE)) and not checked:
                return False
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            if item.checkState() == state:
                return False
            item.setCheckState(state)
            self._refresh_text()
            self.tagsChanged.emit()
            return True
        return False


class BankImportDialog(_BankImportDialogV3):
    """Aktiver Bankimport mit Strg-Auswahl und sicherer Massenbearbeitung."""

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._tag_catalog = tuple(tag.name for tag in self.tags.list_all())
        self._fix_intro_text()
        self._install_bulk_editor()
        self.chk_net_twint.setChecked(False)
        self.chk_net_twint.setToolTip(
            "TWINT-Verrechnung ist bewusst Opt-in: Treffer zuerst prüfen und "
            "erst danach die Verrechnung aktivieren."
        )

    def _fix_intro_text(self) -> None:
        for label in self.findChildren(QLabel):
            if label.text().startswith("Lokaler Review-Import:"):
                label.setText(
                    "Lokaler Review-Import: Typ und Kategorie können pro Zeile "
                    "geändert werden. Kategorie-Tags werden automatisch übernommen; "
                    "weitere vorhandene Tags lassen sich im Tag-Dropdown per "
                    "Checkbox ergänzen. Mehrere Zeilen lassen sich mit Strg+Mausklick "
                    "oder Umschalt+Mausklick auswählen und gemeinsam bearbeiten. "
                    "Die KI lernt erst aus bestätigten Buchungen."
                )
                break

    def _install_bulk_editor(self) -> None:
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
                    f"{typ} · {name}", self._category_token(typ, name)
                )
        self.cmb_bulk_category.setMaxVisibleItems(24)
        bulk.addWidget(self.cmb_bulk_category, 1)

        self.cmb_bulk_tag_action = QComboBox()
        self.cmb_bulk_tag_action.setToolTip(
            "Gewählten Tag bei allen markierten Zeilen hinzufügen oder entfernen"
        )
        self.cmb_bulk_tag_action.addItem("Tag hinzufügen", "add")
        self.cmb_bulk_tag_action.addItem("Tag entfernen", "remove")
        bulk.addWidget(self.cmb_bulk_tag_action)

        self.cmb_bulk_tag = QComboBox()
        self.cmb_bulk_tag.setToolTip("Optionalen Tag für die Mehrfachauswahl wählen")
        self.cmb_bulk_tag.addItem("Tag nicht ändern", "")
        for name in self._tag_catalog:
            self.cmb_bulk_tag.addItem(name, name)
        self.cmb_bulk_tag.setMaxVisibleItems(24)
        bulk.addWidget(self.cmb_bulk_tag)

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
            "Wendet die Dropdown-Einstellungen auf die markierten Zeilen an"
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

    def _populate(self) -> None:
        super()._populate()
        header = self.table.horizontalHeaderItem(self.COL_TAGS)
        if header is not None:
            header.setText("Tags (Kategorie + optional)")
        for row in range(self.table.rowCount()):
            self._install_tag_combo(row)
        self._refresh_effective_view()

    def _install_tag_combo(self, row: int) -> None:
        current = self.table.cellWidget(row, self.COL_TAGS)
        selected: tuple[str, ...] = ()
        if isinstance(current, QLineEdit):
            selected = tuple(
                part.strip() for part in current.text().split(",") if part.strip()
            )
        elif isinstance(current, CheckableTagCombo):
            selected = current.selected_tags()
        fixed = self._category_tag_names(*self._selected_category_identity(row))
        combo = CheckableTagCombo(
            self._tag_catalog,
            selected=selected,
            locked=fixed,
            parent=self.table,
        )
        combo.tagsChanged.connect(
            lambda current_row=row: self._tag_selection_changed(current_row)
        )
        self.table.setCellWidget(row, self.COL_TAGS, combo)

    def _tag_selection_changed(self, _row: int) -> None:
        if not self._updating_row:
            self._refresh_effective_view()

    def _sync_category_tags(self, row: int) -> None:
        widget = self.table.cellWidget(row, self.COL_TAGS)
        if isinstance(widget, CheckableTagCombo):
            fixed = self._category_tag_names(*self._selected_category_identity(row))
            widget.set_locked_tags(fixed)
            return
        super()._sync_category_tags(row)

    def _raw_tag_names(self, row: int) -> tuple[str, ...]:
        widget = self.table.cellWidget(row, self.COL_TAGS)
        if isinstance(widget, CheckableTagCombo):
            return widget.selected_tags()
        return super()._raw_tag_names(row)

    def _tag_names(self, row: int) -> tuple[str, ...]:
        widget = self.table.cellWidget(row, self.COL_TAGS)
        if isinstance(widget, CheckableTagCombo):
            return widget.selected_tags()
        return super()._tag_names(row)

    def _selected_rows(self) -> list[int]:
        selection = self.table.selectionModel()
        if selection is None:
            return []
        rows = {index.row() for index in selection.selectedRows()}
        if not rows:
            rows = {index.row() for index in self.table.selectedIndexes()}
        return sorted(rows)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> bool:
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
        wanted_tag = str(self.cmb_bulk_tag.currentData() or "")
        tag_action = str(self.cmb_bulk_tag_action.currentData() or "add")
        wanted_use = str(self.cmb_bulk_use.currentData() or "")
        if not any((wanted_type, category_token, wanted_tag, wanted_use)):
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
        skipped_required_tag = 0

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
                            self._sync_category_tags(row)
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

                if wanted_tag:
                    tag_combo = self.table.cellWidget(row, self.COL_TAGS)
                    if isinstance(tag_combo, CheckableTagCombo):
                        changed = tag_combo.set_tag_checked(
                            wanted_tag, tag_action == "add"
                        )
                        if changed:
                            changed_rows.add(row)
                        elif (
                            tag_action == "remove"
                            and wanted_tag.casefold()
                            in {name.casefold() for name in tag_combo.locked_tags()}
                        ):
                            skipped_required_tag += 1

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
        if skipped_required_tag:
            notes.append(
                f"{skipped_required_tag} Pflicht-Tags der Kategorie nicht entfernt"
            )
        if skipped_locked:
            notes.append(f"{skipped_locked} gesperrte/duplizierte Zeilen")
        self.lbl_bulk_status.setText(" · ".join(notes))


__all__ = ["BankImportDialog", "CheckableTagCombo"]
