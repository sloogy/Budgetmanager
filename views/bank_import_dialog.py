"""Bankimport-Einstieg mit TWINT als reinem KI-Schein-Typ.

``TWINT (KI)`` ist neben Einkommen/Ausgaben auswählbar, hat aber keinerlei
Budgetwirkung. Für diesen Typ stehen alle Einkommen- und Ausgaben-Kategorien
zur KI-Zuordnung bereit. Positive TWINT-Eingänge werden standardmäßig so
klassifiziert und niemals als Tracking-Einkommen gebucht.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
)

from model.bank_import_ai import match_twint_reimbursement
from model.twint_import_policy import (
    BankImportMarkerStore,
    TYP_TWINT_AI,
    TwintAwareBankImportService,
    is_twint_credit,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from views.bank_import_dialog_v2 import BankImportDialog as _BankImportDialogV2

_CATEGORY_SEPARATOR = "\x1f"


class BankImportDialog(_BankImportDialogV2):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(conn, parent)
        self.service = TwintAwareBankImportService(conn)
        self.ai = self.service.ai
        self.marker_store = BankImportMarkerStore(conn)
        self.twint_credit_indexes: set[int] = set()
        self.marked_twint_indexes: set[int] = set()
        self.ai_marker_indexes: set[int] = set()
        self._ai_policy_initialized: set[int] = set()
        self.table.setHorizontalHeaderItem(
            self.COL_USE,
            QTableWidgetItem("Übernehmen / KI markieren"),
        )

    @staticmethod
    def _default_type(tx):
        return TYP_TWINT_AI if is_twint_credit(tx) else _BankImportDialogV2._default_type(tx)

    def _type_combo(self, typ: str, row: int) -> QComboBox:
        combo = QComboBox()
        combo.addItem(TYP_EXPENSES, TYP_EXPENSES)
        combo.addItem(TYP_INCOME, TYP_INCOME)
        combo.addItem(TYP_TWINT_AI, TYP_TWINT_AI)
        index = combo.findData(typ)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(
            lambda _index, current_row=row: self._type_changed(current_row)
        )
        return combo

    def _row_type(self, row: int) -> str:
        combo = self.table.cellWidget(row, self.COL_TYPE)
        if isinstance(combo, QComboBox):
            value = str(combo.currentData() or "")
            if value in {TYP_EXPENSES, TYP_INCOME, TYP_TWINT_AI}:
                return value
        return super()._row_type(row)

    def _marker_kind(self, index: int) -> str:
        return "twint_credit" if index in self.twint_credit_indexes else "twint_ai"

    def _is_marked_index(self, index: int) -> bool:
        if index in self.twint_credit_indexes:
            return index in self.marked_twint_indexes
        return index in self.ai_marker_indexes

    def _refresh_twint_sets(self) -> None:
        self.twint_credit_indexes = {
            index
            for index, tx in enumerate(self.transactions)
            if is_twint_credit(tx)
        }
        if not self.document_digest:
            self.marked_twint_indexes = set()
            self.ai_marker_indexes = set()
            return
        self.marked_twint_indexes = self.marker_store.marked_indexes(
            self.transactions,
            self.document_digest,
            marker_kind="twint_credit",
        )
        self.ai_marker_indexes = self.marker_store.marked_indexes(
            self.transactions,
            self.document_digest,
            marker_kind="twint_ai",
        )

    def _build_matches(self) -> None:
        """Bereits verbrauchte TWINT-Gutschriften nicht erneut matchen."""
        self._refresh_twint_sets()
        self.matches.clear()
        self.matched_credit_indexes.clear()
        credits = [
            self._signal(index, tx)
            for index, tx in enumerate(self.transactions)
            if tx.amount > 0
            and index not in self.duplicate_indexes
            and index not in self.marked_twint_indexes
        ]
        for index, tx in enumerate(self.transactions):
            if tx.amount >= 0 or index in self.duplicate_indexes:
                continue
            match = match_twint_reimbursement(self._signal(index, tx), credits)
            if match is None:
                continue
            try:
                credit_index = int(match.credit_id.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            if (
                credit_index in self.matched_credit_indexes
                or credit_index in self.marked_twint_indexes
            ):
                continue
            self.matches[index] = match
            self.matched_credit_indexes.add(credit_index)

    @staticmethod
    def _category_token(category_typ: str, category: str) -> str:
        return f"{category_typ}{_CATEGORY_SEPARATOR}{category}"

    @staticmethod
    def _decode_category_token(value: object) -> tuple[str, str]:
        text = str(value or "")
        if _CATEGORY_SEPARATOR not in text:
            return "", ""
        typ, category = text.split(_CATEGORY_SEPARATOR, 1)
        if typ not in {TYP_EXPENSES, TYP_INCOME}:
            return "", ""
        return typ, category

    def _ai_category_combo(self, index: int) -> QComboBox:
        tx = self.transactions[index]
        combo = QComboBox()
        combo.addItem("— Kategorie nur für KI wählen —", "")
        for typ in (TYP_EXPENSES, TYP_INCOME):
            for name in self.categories.list_names(typ):
                combo.addItem(
                    f"{typ} · {name}",
                    self._category_token(typ, name),
                )

        marker_kind = self._marker_kind(index)
        preferred = self.marker_store.classification(
            tx,
            self.document_digest,
            marker_kind=marker_kind,
        )
        if not all(preferred):
            preferred = self.marker_store.suggest_category(tx)
        if all(preferred):
            wanted = self._category_token(*preferred)
            found = combo.findData(wanted)
            if found >= 0:
                combo.setCurrentIndex(found)
        return combo

    def _selected_ai_category(self, row: int) -> tuple[str, str]:
        combo = self.table.cellWidget(row, self.COL_CATEGORY)
        if not isinstance(combo, QComboBox):
            return "", ""
        return self._decode_category_token(combo.currentData())

    def _set_prediction_for_row(self, row: int, *, replace_tags: bool) -> None:
        if self._row_type(row) != TYP_TWINT_AI:
            super()._set_prediction_for_row(row, replace_tags=replace_tags)
            return

        use_item = self.table.item(row, self.COL_USE)
        if use_item is None:
            return
        index = int(use_item.data(Qt.UserRole))
        self.table.setCellWidget(row, self.COL_CATEGORY, self._ai_category_combo(index))

        tags_edit = self.table.cellWidget(row, self.COL_TAGS)
        if isinstance(tags_edit, QLineEdit):
            tags_edit.blockSignals(True)
            tags_edit.clear()
            tags_edit.setPlaceholderText("TWINT-KI: Kategorie reicht")
            tags_edit.setEnabled(False)
            tags_edit.blockSignals(False)

        suggested = self.marker_store.suggest_category(self.transactions[index])
        label = "TWINT-KI gelernt" if all(suggested) else "TWINT-KI"
        ai_item = self.table.item(row, self.COL_AI)
        if ai_item is None:
            self.table.setItem(row, self.COL_AI, QTableWidgetItem(label))
        else:
            ai_item.setText(label)

    def _type_changed(self, row: int) -> None:
        if self._updating_row:
            return
        self._updating_row = True
        try:
            typ = self._row_type(row)
            self._set_prediction_for_row(row, replace_tags=True)
            tags_edit = self.table.cellWidget(row, self.COL_TAGS)
            if isinstance(tags_edit, QLineEdit) and typ != TYP_TWINT_AI:
                tags_edit.setEnabled(True)
                tags_edit.setPlaceholderText("vorhandene Tags, mit Komma getrennt")
        finally:
            self._updating_row = False
        self._refresh_effective_view()

    def _populate(self) -> None:
        self._refresh_twint_sets()
        self._ai_policy_initialized.clear()
        super()._populate()
        self._apply_ai_policy()

    def _effective_amount(
        self,
        index: int,
        row: int,
        *,
        strict_tags: bool = False,
    ) -> tuple[float, str]:
        if self._row_type(row) == TYP_TWINT_AI:
            return 0.0, "twint_ai"
        return super()._effective_amount(
            index,
            row,
            strict_tags=strict_tags,
        )

    def _apply_ai_policy(self) -> None:
        for row in range(self.table.rowCount()):
            if self._row_type(row) != TYP_TWINT_AI:
                continue
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            marked = self._is_marked_index(index)
            matched = index in self.matched_credit_indexes

            use_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            if row not in self._ai_policy_initialized:
                use_item.setCheckState(Qt.Unchecked if marked else Qt.Checked)
                self._ai_policy_initialized.add(row)

            if marked:
                status = "TWINT-KI · bereits markiert · 0.00 Budgetwirkung"
            elif matched:
                status = "TWINT-KI · nur lernen · passender Ausgabe zugeordnet"
            else:
                status = "TWINT-KI · nur lernen · nicht buchen"

            status_item = self.table.item(row, self.COL_TWINT)
            if status_item is not None:
                status_item.setText(status)
            effective_item = self.table.item(row, self.COL_EFFECTIVE)
            if effective_item is not None:
                effective_item.setText("0.00")
        self._update_summary()

    def _refresh_effective_view(self) -> None:
        super()._refresh_effective_view()
        self._apply_ai_policy()

    def _update_summary(self) -> None:
        super()._update_summary()
        ai_selected = 0
        for row in range(self.table.rowCount()):
            if self._row_type(row) != TYP_TWINT_AI:
                continue
            item = self.table.item(row, self.COL_USE)
            if item is not None and item.checkState() == Qt.Checked:
                ai_selected += 1
        if ai_selected or self.twint_credit_indexes:
            self.lbl_summary.setText(
                self.lbl_summary.text()
                + f" · {ai_selected} TWINT-KI-Zuordnungen"
            )

    def _build_item(self, row: int):
        if self._row_type(row) == TYP_TWINT_AI:
            return None
        return super()._build_item(row)

    def import_selected(self) -> None:
        if not self.transactions or not self.document_digest:
            QMessageBox.information(
                self,
                "Bankimport",
                "Bitte zuerst eine PDF- oder CSV-Datei öffnen.",
            )
            return

        plan = []
        twint_classifications = []
        ai_classifications = []
        try:
            for row in range(self.table.rowCount()):
                use_item = self.table.item(row, self.COL_USE)
                if use_item is None or use_item.checkState() != Qt.Checked:
                    continue
                index = int(use_item.data(Qt.UserRole))
                if self._row_type(row) == TYP_TWINT_AI:
                    category_typ, category = self._selected_ai_category(row)
                    if not category:
                        raise ValueError(
                            f"Zeile {row + 1}: Für TWINT (KI) bitte eine "
                            "Kategorie aus Einkommen oder Ausgaben wählen."
                        )
                    target = (
                        twint_classifications
                        if index in self.twint_credit_indexes
                        else ai_classifications
                    )
                    target.append(
                        (self.transactions[index], category_typ, category)
                    )
                    continue
                item = super()._build_item(row)
                if item is not None:
                    plan.append(item)
        except ValueError as exc:
            QMessageBox.warning(self, "Import prüfen", str(exc))
            return

        ai_count = len(twint_classifications) + len(ai_classifications)
        if not plan and not ai_count:
            QMessageBox.information(
                self,
                "Bankimport",
                "Keine neuen Budgetbuchungen oder KI-Zuordnungen ausgewählt.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Bankimport bestätigen",
            f"{len(plan)} Budgetbuchungen importieren und {ai_count} "
            "TWINT-KI-Zuordnungen lernen?\n\n"
            "TWINT (KI) erzeugt niemals eine Budgetbuchung.",
        )
        if answer != QMessageBox.Yes:
            return

        imported = 0
        skipped = 0
        try:
            if plan:
                result = self.service.import_items(
                    plan,
                    document_digest=self.document_digest,
                )
                imported = result.imported
                skipped = result.skipped_duplicates
        except (sqlite3.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Bankimport fehlgeschlagen",
                "Es wurde nichts aus diesem Budget-Batch übernommen.\n\n" + str(exc),
            )
            return

        learned = 0
        try:
            if twint_classifications:
                self.marker_store.mark_classifications(
                    twint_classifications,
                    self.document_digest,
                    marker_kind="twint_credit",
                )
                learned += len(twint_classifications)
            if ai_classifications:
                self.marker_store.mark_classifications(
                    ai_classifications,
                    self.document_digest,
                    marker_kind="twint_ai",
                )
                learned += len(ai_classifications)
        except (sqlite3.Error, ValueError) as exc:
            QMessageBox.warning(
                self,
                "KI-Zuordnung unvollständig",
                f"{imported} Budgetbuchungen wurden übernommen, aber die "
                f"TWINT-KI-Zuordnung konnte nicht vollständig gespeichert werden: {exc}\n\n"
                "TWINT wurde trotzdem nicht als Einkommen gebucht.",
            )
            return

        QMessageBox.information(
            self,
            "Bankimport abgeschlossen",
            f"{imported} Budgetbuchungen importiert; {skipped} Duplikate "
            f"übersprungen; {learned} TWINT-KI-Zuordnungen gelernt. "
            "TWINT-KI hat 0.00 Budgetwirkung.",
        )
        self.accept()


__all__ = ["BankImportDialog"]
