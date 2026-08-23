"""Kanonischer Einstiegspunkt für den aktuellen Bankimport-Dialog.

Ergänzt den V3-Review-Import um sichere Mehrfachauswahl, Dropdown-
Massenbearbeitung, eine checkbare und durchsuchbare Tag-Auswahl, globale
Importsuche, sichere Sortierung und den gemeinsamen Review mehrerer Dateien.
Kategorie-Tags bleiben verbindlich; zusätzliche vorhandene Tags können bewusst
ergänzt werden.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.bank_import_service import source_digest
from model.bank_statement_reader import BankStatementError, load_transactions
from model.credit_card_statement_reader import is_credit_card_csv, load_credit_card_csv
from model.twint_import_policy import TYP_TWINT_AI, is_twint_credit
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from utils.i18n import tr
from utils.money import get_currency
from utils.notifications import show_info, show_warning
from views.bank_import_dialog_v3 import BankImportDialog as _BankImportDialogV3


class CheckableTagCombo(QComboBox):
    """Dropdown mit Checkboxen und Suche für bekannte Tags.

    Kategorie-Tags werden als gesperrte Pflicht-Tags angezeigt. Zusätzliche
    Tags sind frei an-/abwählbar, ohne dass freie Texte oder unbekannte Tags
    in den Import gelangen können. Beim Öffnen dient das Eingabefeld als
    Live-Suche; beim Schließen wird wieder die Tag-Zusammenfassung angezeigt.
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
            line_edit.setReadOnly(False)
            line_edit.setPlaceholderText(tr("bank_import.tags_placeholder"))
            line_edit.textEdited.connect(self._filter_items)
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
        for name in sorted(tag_names, key=str.casefold):
            item = QStandardItem(name)
            item.setCheckable(True)
            item.setData(name, self._NAME_ROLE)
            is_locked = self._key(name) in locked_keys
            item.setData(is_locked, self._LOCK_ROLE)
            if is_locked:
                item.setText(f"🔒 {name}")
                item.setToolTip(tr("bank_import.tag_required_tip"))
            item.setCheckState(
                Qt.CheckState.Checked
                if is_locked or self._key(name) in selected_keys
                else Qt.CheckState.Unchecked
            )
            model.appendRow(item)
        self._refresh_text()

    def showPopup(self) -> None:
        self._filter_items("")
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.clear()
            line_edit.setPlaceholderText(tr("search.placeholder"))
        super().showPopup()
        if line_edit is not None:
            line_edit.setFocus()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._filter_items("")
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(tr("bank_import.tags_placeholder"))
        self._refresh_text()

    def _filter_items(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            name = str(item.data(self._NAME_ROLE) or "") if item is not None else ""
            self.view().setRowHidden(row, bool(query) and query not in name.casefold())

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
        if line_edit is not None and not self.view().isVisible():
            line_edit.setText(text)
        self.setToolTip(text or tr("bank_import.no_tags_selected"))

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

    def set_selected_tags(self, selected: tuple[str, ...]) -> None:
        """Stellt optionale Tags wieder her; Pflicht-Tags bleiben immer gesetzt."""
        wanted = {self._key(name) for name in selected}
        model = self.model()
        changed = False
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            locked = bool(item.data(self._LOCK_ROLE))
            name = self._key(item.data(self._NAME_ROLE))
            state = (
                Qt.CheckState.Checked
                if locked or name in wanted
                else Qt.CheckState.Unchecked
            )
            if item.checkState() != state:
                item.setCheckState(state)
                changed = True
        self._refresh_text()
        if changed:
            self.tagsChanged.emit()

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
    """Aktiver Bankimport mit Mehrdatei-Review und sicherer Massenbearbeitung."""

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._tag_catalog = tuple(
            sorted((tag.name for tag in self.tags.list_all()), key=str.casefold)
        )
        self._transaction_digests: list[str] = []
        self._original_order: dict[tuple[str, str, int], int] = {}
        self._fix_intro_text()
        self._install_bulk_editor()
        self._install_search_and_sort()
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
                    "Checkbox ergänzen und durchsuchen. Mehrere Zeilen lassen sich "
                    "mit Strg+Mausklick oder Umschalt+Mausklick auswählen und "
                    "gemeinsam bearbeiten. Mehrere CSV/PDF-Dateien können in einem "
                    "Review geladen, durchsucht und sortiert werden. Die KI lernt "
                    "erst aus bestätigten Buchungen."
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
        bulk.addWidget(QLabel(tr("bank_import.bulk_label")))

        self.cmb_bulk_type = QComboBox()
        self.cmb_bulk_type.setToolTip(tr("bank_import.bulk_type_tip"))
        self.cmb_bulk_type.addItem(tr("bank_import.bulk_type_keep"), "")
        self.cmb_bulk_type.addItem(TYP_EXPENSES, TYP_EXPENSES)
        self.cmb_bulk_type.addItem(TYP_INCOME, TYP_INCOME)
        self.cmb_bulk_type.addItem(TYP_TWINT_AI, TYP_TWINT_AI)
        bulk.addWidget(self.cmb_bulk_type)

        self.cmb_bulk_category = QComboBox()
        self.cmb_bulk_category.setToolTip(
            "Kategorie für kompatible ausgewählte Zeilen setzen"
        )
        self.cmb_bulk_category.addItem(tr("bank_import.bulk_category_keep"), "")
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
        self.cmb_bulk_tag_action.addItem(tr("bank_import.bulk_tag_add"), "add")
        self.cmb_bulk_tag_action.addItem(tr("bank_import.bulk_tag_remove"), "remove")
        bulk.addWidget(self.cmb_bulk_tag_action)

        self.cmb_bulk_tag = QComboBox()
        self.cmb_bulk_tag.setToolTip(tr("bank_import.bulk_tag_tip"))
        self.cmb_bulk_tag.addItem(tr("bank_import.bulk_tag_keep"), "")
        for name in self._tag_catalog:
            self.cmb_bulk_tag.addItem(name, name)
        self.cmb_bulk_tag.setMaxVisibleItems(24)
        bulk.addWidget(self.cmb_bulk_tag)

        self.cmb_bulk_use = QComboBox()
        self.cmb_bulk_use.setToolTip(
            "Übernahme/KI-Markierung für alle ausgewählten Zeilen setzen"
        )
        self.cmb_bulk_use.addItem(tr("bank_import.bulk_use_keep"), "")
        self.cmb_bulk_use.addItem(tr("bank_import.bulk_use_checked"), "checked")
        self.cmb_bulk_use.addItem(tr("bank_import.bulk_use_unchecked"), "unchecked")
        bulk.addWidget(self.cmb_bulk_use)

        self.btn_bulk_apply = QPushButton(tr("bank_import.bulk_apply"))
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

    def _install_search_and_sort(self) -> None:
        tools = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search.placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setToolTip(
            "Filtert Datum, Typ, Betrag, Buchungstext, Kategorie, Tags, Status "
            "und Quelldatei ohne die Importauswahl zu verändern."
        )
        self.search_input.textChanged.connect(self._apply_search_filter)
        tools.addWidget(self.search_input, 1)

        tools.addWidget(QLabel("Sortierung:"))
        self.cmb_sort = QComboBox()
        self.cmb_sort.addItem("Originalreihenfolge", "original")
        self.cmb_sort.addItem("Datum: neu → alt", "date_desc")
        self.cmb_sort.addItem("Datum: alt → neu", "date_asc")
        self.cmb_sort.addItem("Betrag: hoch → tief", "amount_desc")
        self.cmb_sort.addItem("Betrag: tief → hoch", "amount_asc")
        self.cmb_sort.addItem("Buchungstext: A → Z", "text_asc")
        self.cmb_sort.addItem("Kategorie: A → Z", "category_asc")
        self.cmb_sort.addItem("Tags: A → Z", "tags_asc")
        self.cmb_sort.addItem("Quelldatei: A → Z", "source_asc")
        self.cmb_sort.setToolTip(
            "Sortiert sicher und erhält manuelle Typ-, Kategorie-, Tag- und "
            "Import-Auswahlen."
        )
        self.cmb_sort.currentIndexChanged.connect(self._sort_rows)
        tools.addWidget(self.cmb_sort)

        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertLayout(3, tools)

    def _digest_for_index(self, index: int) -> str:
        if 0 <= index < len(self._transaction_digests):
            return self._transaction_digests[index]
        return self.document_digest

    def _transaction_key(self, index: int) -> tuple[str, str, int]:
        tx = self.transactions[index]
        return (
            self._digest_for_index(index),
            str(tx.source_name or ""),
            int(tx.source_index),
        )

    def _capture_row_states(self) -> dict[tuple[str, str, int], dict[str, object]]:
        states: dict[tuple[str, str, int], dict[str, object]] = {}
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            category_combo = self.table.cellWidget(row, self.COL_CATEGORY)
            tag_combo = self.table.cellWidget(row, self.COL_TAGS)
            states[self._transaction_key(index)] = {
                "use": use_item.checkState(),
                "typ": self._row_type(row),
                "category": (
                    category_combo.currentData()
                    if isinstance(category_combo, QComboBox)
                    else ""
                ),
                "tags": (
                    tag_combo.selected_tags()
                    if isinstance(tag_combo, CheckableTagCombo)
                    else ()
                ),
            }
        return states

    def _restore_row_states(
        self,
        states: dict[tuple[str, str, int], dict[str, object]],
    ) -> None:
        self._updating_row = True
        try:
            for row in range(self.table.rowCount()):
                use_item = self.table.item(row, self.COL_USE)
                if use_item is None:
                    continue
                index = int(use_item.data(Qt.UserRole))
                state = states.get(self._transaction_key(index))
                if not state:
                    continue

                typ = str(state.get("typ") or "")
                type_combo = self.table.cellWidget(row, self.COL_TYPE)
                if isinstance(type_combo, QComboBox):
                    self._set_combo_data(type_combo, typ)
                    self._set_prediction_for_row(row, replace_tags=False)

                category_combo = self.table.cellWidget(row, self.COL_CATEGORY)
                if isinstance(category_combo, QComboBox):
                    category = state.get("category")
                    wanted = category_combo.findData(category)
                    if wanted >= 0:
                        category_combo.blockSignals(True)
                        try:
                            category_combo.setCurrentIndex(wanted)
                        finally:
                            category_combo.blockSignals(False)
                self._sync_category_tags(row)

                tag_combo = self.table.cellWidget(row, self.COL_TAGS)
                if isinstance(tag_combo, CheckableTagCombo):
                    tag_combo.set_selected_tags(tuple(state.get("tags") or ()))

                if use_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    use_item.setCheckState(state["use"])
        finally:
            self._updating_row = False
        self._refresh_effective_view()

    def _sort_rows(self, _index: int = -1) -> None:
        if not self.transactions or not hasattr(self, "cmb_sort"):
            return
        mode = str(self.cmb_sort.currentData() or "original")
        states = self._capture_row_states()
        duplicates = {
            self._transaction_key(index)
            for index in self.duplicate_indexes
            if 0 <= index < len(self.transactions)
        }
        records = [
            (tx, self._digest_for_index(index), self._transaction_key(index))
            for index, tx in enumerate(self.transactions)
        ]

        def state_text(key, field: str) -> str:
            value = states.get(key, {}).get(field, "")
            if isinstance(value, tuple):
                return ", ".join(str(part) for part in value).casefold()
            return str(value or "").casefold()

        reverse = mode in {"date_desc", "amount_desc"}
        if mode == "original":
            key_func = lambda record: self._original_order.get(record[2], 0)
        elif mode in {"date_desc", "date_asc"}:
            key_func = lambda record: record[0].booking_date
        elif mode in {"amount_desc", "amount_asc"}:
            key_func = lambda record: abs(float(record[0].amount))
        elif mode == "text_asc":
            key_func = lambda record: str(record[0].description or "").casefold()
        elif mode == "category_asc":
            key_func = lambda record: state_text(record[2], "category")
        elif mode == "tags_asc":
            key_func = lambda record: state_text(record[2], "tags")
        elif mode == "source_asc":
            key_func = lambda record: str(record[0].source_name or "").casefold()
        else:
            return

        records.sort(key=key_func, reverse=reverse)
        self.transactions = [record[0] for record in records]
        self._transaction_digests = [record[1] for record in records]
        self.duplicate_indexes = {
            index for index, record in enumerate(records) if record[2] in duplicates
        }
        self._build_matches()
        self._populate()
        self._restore_row_states(states)
        self._apply_search_filter()

    def _apply_search_filter(self, _text: str = "") -> None:
        if not hasattr(self, "search_input"):
            return
        query = self.search_input.text().strip().casefold()
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                self.table.setRowHidden(row, False)
                continue
            index = int(use_item.data(Qt.UserRole))
            tx = self.transactions[index]
            category_combo = self.table.cellWidget(row, self.COL_CATEGORY)
            tag_combo = self.table.cellWidget(row, self.COL_TAGS)
            values = [
                tx.booking_date.strftime("%d.%m.%Y"),
                str(tx.amount),
                tx.currency,
                tx.description,
                tx.counterparty,
                tx.source_name,
                self._row_type(row),
                (
                    category_combo.currentText()
                    if isinstance(category_combo, QComboBox)
                    else ""
                ),
                (
                    ", ".join(tag_combo.selected_tags())
                    if isinstance(tag_combo, CheckableTagCombo)
                    else ""
                ),
            ]
            for column in (self.COL_AI, self.COL_TWINT, self.COL_EFFECTIVE):
                item = self.table.item(row, column)
                if item is not None:
                    values.append(item.text())
            haystack = " ".join(str(value or "") for value in values).casefold()
            self.table.setRowHidden(row, bool(query) and query not in haystack)

    def open_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Kontoauszüge wählen",
            "",
            "Kontoauszüge (*.csv *.pdf);;CSV (*.csv);;PDF (*.pdf)",
        )
        if not paths:
            return

        transactions = []
        digests: list[str] = []
        duplicate_indexes: set[int] = set()
        formats: list[str] = []
        valid_paths: list[str] = []
        errors: list[str] = []
        currency = get_currency().upper()

        for path in paths:
            try:
                if is_credit_card_csv(path):
                    file_transactions = load_credit_card_csv(path, currency)
                    source_format = "Kreditkarten-CSV"
                else:
                    file_transactions = load_transactions(path, currency)
                    source_format = "Bank-CSV/PDF"
                digest = source_digest(path)
            except (BankStatementError, OSError, ValueError) as exc:
                errors.append(f"{Path(path).name}: {exc}")
                continue

            offset = len(transactions)
            local_duplicates = self.service.duplicate_indexes(file_transactions, digest)
            duplicate_indexes.update(offset + index for index in local_duplicates)
            transactions.extend(file_transactions)
            digests.extend(digest for _tx in file_transactions)
            formats.append(source_format)
            valid_paths.append(path)

        if not transactions:
            details = "\n".join(errors) if errors else "Keine Buchungen erkannt."
            show_warning(self, "Import nicht möglich", details)
            return

        self.transactions = transactions
        self._transaction_digests = digests
        self.document_digest = digests[0]
        self.source_format = " + ".join(sorted(set(formats)))
        self.duplicate_indexes = duplicate_indexes
        self._original_order = {
            self._transaction_key(index): index for index in range(len(transactions))
        }
        if hasattr(self, "cmb_sort"):
            self.cmb_sort.blockSignals(True)
            try:
                self.cmb_sort.setCurrentIndex(0)
            finally:
                self.cmb_sort.blockSignals(False)
        if hasattr(self, "search_input"):
            self.search_input.clear()

        if len(valid_paths) == 1:
            self.lbl_file.setText(
                f"{Path(valid_paths[0]).name} · {self.source_format}"
            )
        else:
            self.lbl_file.setText(
                f"{len(valid_paths)} Dateien · {len(transactions)} Buchungen · "
                f"{self.source_format}"
            )
        self._build_matches()
        self._populate()

        if errors:
            show_warning(
                self,
                "Einige Dateien wurden übersprungen",
                "Die übrigen Dateien wurden geladen:\n\n" + "\n".join(errors),
            )

    def _refresh_twint_sets(self) -> None:
        self.twint_credit_indexes = {
            index for index, tx in enumerate(self.transactions) if is_twint_credit(tx)
        }
        self.marked_twint_indexes = set()
        self.ai_marker_indexes = set()
        if not self.transactions:
            return

        groups: dict[str, list[int]] = defaultdict(list)
        for index in range(len(self.transactions)):
            groups[self._digest_for_index(index)].append(index)

        for digest, global_indexes in groups.items():
            grouped_transactions = [self.transactions[index] for index in global_indexes]
            twint_marked = self.marker_store.marked_indexes(
                grouped_transactions,
                digest,
                marker_kind="twint_credit",
            )
            ai_marked = self.marker_store.marked_indexes(
                grouped_transactions,
                digest,
                marker_kind="twint_ai",
            )
            self.marked_twint_indexes.update(
                global_indexes[local_index] for local_index in twint_marked
            )
            self.ai_marker_indexes.update(
                global_indexes[local_index] for local_index in ai_marked
            )

    def _ai_category_combo(self, index: int, row: int) -> QComboBox:
        original_digest = self.document_digest
        self.document_digest = self._digest_for_index(index)
        try:
            return super()._ai_category_combo(index, row)
        finally:
            self.document_digest = original_digest

    def _type_combo(self, typ: str, row: int) -> QComboBox:
        """Positive TWINT-Eingänge dürfen nie als Budgetbuchung angeboten werden."""
        use_item = self.table.item(row, self.COL_USE)
        if use_item is not None:
            try:
                tx_index = int(use_item.data(Qt.UserRole))
            except (TypeError, ValueError):
                tx_index = -1
            in_range = 0 <= tx_index < len(self.transactions)
            if in_range and is_twint_credit(self.transactions[tx_index]):
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
            header.setText(tr("bank_import.col_tags_header"))
        for row in range(self.table.rowCount()):
            self._install_tag_combo(row)
        self._refresh_effective_view()
        self._apply_search_filter()

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
            self._apply_search_filter()

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
            show_info(
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
            show_info(
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
                    compatible = current_type in (TYP_TWINT_AI, category_typ)
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
                        elif tag_action == "remove" and wanted_tag.casefold() in {
                            name.casefold() for name in tag_combo.locked_tags()
                        }:
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
        self._apply_search_filter()

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

    def import_selected(self) -> None:
        if not self.transactions or not self.document_digest:
            show_info(
                self,
                "Bankimport",
                "Bitte zuerst eine oder mehrere PDF-/CSV-Dateien öffnen.",
            )
            return

        plan_groups: dict[str, list] = defaultdict(list)
        twint_groups: dict[str, list] = defaultdict(list)
        ai_groups: dict[str, list] = defaultdict(list)
        try:
            for row in range(self.table.rowCount()):
                use_item = self.table.item(row, self.COL_USE)
                if use_item is None or use_item.checkState() != Qt.Checked:
                    continue
                index = int(use_item.data(Qt.UserRole))
                digest = self._digest_for_index(index)
                if self._row_type(row) == TYP_TWINT_AI:
                    category_typ, category = self._selected_ai_category(row)
                    if not category:
                        raise ValueError(
                            f"Zeile {row + 1}: Für TWINT (KI) bitte eine "
                            "Kategorie aus Einkommen oder Ausgaben wählen."
                        )
                    target = (
                        twint_groups
                        if index in self.twint_credit_indexes
                        else ai_groups
                    )
                    target[digest].append(
                        (self.transactions[index], category_typ, category)
                    )
                    continue
                item = super()._build_item(row)
                if item is not None:
                    plan_groups[digest].append(item)
        except ValueError as exc:
            show_warning(self, "Import prüfen", str(exc))
            return

        plan_count = sum(len(items) for items in plan_groups.values())
        ai_count = sum(len(items) for items in twint_groups.values()) + sum(
            len(items) for items in ai_groups.values()
        )
        if not plan_count and not ai_count:
            show_info(
                self,
                "Bankimport",
                "Keine neuen Budgetbuchungen oder KI-Zuordnungen ausgewählt.",
            )
            return

        file_count = len(
            set(plan_groups) | set(twint_groups) | set(ai_groups)
        )
        answer = QMessageBox.question(
            self,
            "Bankimport bestätigen",
            f"{plan_count} Budgetbuchungen importieren und {ai_count} "
            f"TWINT-KI-Zuordnungen aus {file_count} Datei(en) lernen?\n\n"
            "Jede Quelldatei behält ihre eigene Duplikat-ID und wird als "
            "eigener atomarer Batch verarbeitet. TWINT (KI) erzeugt niemals "
            "eine Budgetbuchung.",
        )
        if answer != QMessageBox.Yes:
            return

        imported = 0
        skipped = 0
        completed_budget_batches = 0
        try:
            for digest, plan in plan_groups.items():
                result = self.service.import_items(plan, document_digest=digest)
                imported += result.imported
                skipped += result.skipped_duplicates
                completed_budget_batches += 1
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            show_warning(
                self,
                "Bankimport teilweise fehlgeschlagen",
                f"{imported} Buchungen aus {completed_budget_batches} Datei-Batches "
                f"wurden bereits übernommen. Der nächste Batch schlug fehl:\n\n{exc}",
            )
            return

        learned = 0
        try:
            for digest, classifications in twint_groups.items():
                self.marker_store.mark_classifications(
                    classifications,
                    digest,
                    marker_kind="twint_credit",
                )
                learned += len(classifications)
            for digest, classifications in ai_groups.items():
                self.marker_store.mark_classifications(
                    classifications,
                    digest,
                    marker_kind="twint_ai",
                )
                learned += len(classifications)
        except ValueError as exc:
            show_warning(
                self,
                "KI-Zuordnung unvollständig",
                f"{imported} Budgetbuchungen wurden übernommen, aber die "
                f"TWINT-KI-Zuordnung konnte nicht vollständig gespeichert werden: {exc}\n\n"
                "TWINT wurde trotzdem nicht als Einkommen gebucht.",
            )
            return

        show_info(
            self,
            "Bankimport abgeschlossen",
            f"{imported} Budgetbuchungen importiert; {skipped} Duplikate "
            f"übersprungen; {learned} TWINT-KI-Zuordnungen gelernt. "
            "Mehrere Quelldateien wurden getrennt idempotent verarbeitet; "
            "Tags wurden aus den Kategorien übernommen bzw. bewusst ergänzt.",
        )
        self.accept()


__all__ = ["BankImportDialog", "CheckableTagCombo"]
