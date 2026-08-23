"""Kompatibler Einstiegspunkt für den Bankimport-Dialog.

Ergänzt V2 um die Budgetregel, dass positive TWINT-Eingänge ausschließlich
als Erstattungs-/Zuordnungssignal markiert werden. Sie erzeugen niemals eine
Einkommensbuchung.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QMessageBox, QTableWidgetItem

from model.twint_import_policy import (
    BankImportMarkerStore,
    TwintAwareBankImportService,
    is_twint_credit,
)
from views.bank_import_dialog_v2 import BankImportDialog as _BankImportDialogV2


class BankImportDialog(_BankImportDialogV2):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(conn, parent)
        # Sicherheitsgurt auf Service-Ebene: Auch bei einem späteren UI-Fehler
        # darf ein positiver TWINT-Eingang nicht im Tracking landen.
        self.service = TwintAwareBankImportService(conn)
        self.ai = self.service.ai
        self.marker_store = BankImportMarkerStore(conn)
        self.twint_credit_indexes: set[int] = set()
        self.marked_twint_indexes: set[int] = set()
        self.table.setHorizontalHeaderItem(self.COL_USE, QTableWidgetItem("Übernehmen"))

    def _type_changed(self, row: int) -> None:
        if self._updating_row:
            return
        use_item = self.table.item(row, self.COL_USE)
        if use_item is not None:
            index = int(use_item.data(Qt.UserRole))
            if index in self.twint_credit_indexes:
                return
        self._updating_row = True
        try:
            self._set_prediction_for_row(row, replace_tags=True)
        finally:
            self._updating_row = False
        self._refresh_effective_view()

    def _populate(self) -> None:
        self.twint_credit_indexes = {
            index
            for index, tx in enumerate(self.transactions)
            if is_twint_credit(tx)
        }
        self.marked_twint_indexes = (
            self.marker_store.marked_indexes(
                self.transactions,
                self.document_digest,
            )
            if self.document_digest
            else set()
        )
        super()._populate()
        self._apply_twint_policy()

    def _set_prediction_for_row(self, row: int, *, replace_tags: bool) -> None:
        use_item = self.table.item(row, self.COL_USE)
        if use_item is None:
            return
        index = int(use_item.data(Qt.UserRole))
        if index not in self.twint_credit_indexes:
            super()._set_prediction_for_row(row, replace_tags=replace_tags)
            return

        type_combo = self.table.cellWidget(row, self.COL_TYPE)
        if isinstance(type_combo, QComboBox):
            type_combo.blockSignals(True)
            type_combo.clear()
            type_combo.addItem("TWINT-Erstattung (nicht buchen)", "twint_marker")
            type_combo.setEnabled(False)
            type_combo.blockSignals(False)

        category_combo = QComboBox()
        category_combo.addItem("— nur markieren, keine Kategorie —", "")
        category_combo.setEnabled(False)
        self.table.setCellWidget(row, self.COL_CATEGORY, category_combo)

        tags_edit = self.table.cellWidget(row, self.COL_TAGS)
        if isinstance(tags_edit, QLineEdit):
            tags_edit.blockSignals(True)
            tags_edit.clear()
            tags_edit.setEnabled(False)
            tags_edit.blockSignals(False)

        ai_item = self.table.item(row, self.COL_AI)
        if ai_item is None:
            self.table.setItem(row, self.COL_AI, QTableWidgetItem("TWINT-Marker"))
        else:
            ai_item.setText("TWINT-Marker")

    def _apply_twint_policy(self) -> None:
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            if index not in self.twint_credit_indexes:
                continue

            already_marked = index in self.marked_twint_indexes
            matched = index in self.matched_credit_indexes
            if already_marked:
                use_item.setFlags(Qt.ItemIsEnabled)
                use_item.setCheckState(Qt.Unchecked)
                status = "TWINT-Eingang · bereits markiert · nicht gebucht"
            else:
                use_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                use_item.setCheckState(Qt.Checked)
                status = (
                    "TWINT-Erstattung · nur markieren · Ausgabe zugeordnet"
                    if matched
                    else "TWINT-Eingang · nur markieren · nicht buchen"
                )

            type_combo = self.table.cellWidget(row, self.COL_TYPE)
            if isinstance(type_combo, QComboBox):
                type_combo.setEnabled(False)
            category_combo = self.table.cellWidget(row, self.COL_CATEGORY)
            if isinstance(category_combo, QComboBox):
                category_combo.setEnabled(False)
            tags_edit = self.table.cellWidget(row, self.COL_TAGS)
            if isinstance(tags_edit, QLineEdit):
                tags_edit.setEnabled(False)

            status_item = self.table.item(row, self.COL_TWINT)
            if status_item is not None:
                status_item.setText(status)
            effective_item = self.table.item(row, self.COL_EFFECTIVE)
            if effective_item is not None:
                effective_item.setText("0.00")
        self._update_summary()

    def _refresh_effective_view(self) -> None:
        super()._refresh_effective_view()
        self._apply_twint_policy()

    def _update_summary(self) -> None:
        super()._update_summary()
        pending_markers = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_USE)
            if item is None:
                continue
            index = int(item.data(Qt.UserRole))
            if (
                index in self.twint_credit_indexes
                and index not in self.marked_twint_indexes
                and item.checkState() == Qt.Checked
            ):
                pending_markers += 1
        if self.twint_credit_indexes:
            self.lbl_summary.setText(
                self.lbl_summary.text()
                + f" · {pending_markers} TWINT nur markieren"
                + f" · {len(self.marked_twint_indexes)} TWINT bereits markiert"
            )

    def _build_item(self, row: int):
        use_item = self.table.item(row, self.COL_USE)
        if use_item is not None:
            index = int(use_item.data(Qt.UserRole))
            if index in self.twint_credit_indexes:
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
        mark_only = []
        try:
            for row in range(self.table.rowCount()):
                use_item = self.table.item(row, self.COL_USE)
                if use_item is None or use_item.checkState() != Qt.Checked:
                    continue
                index = int(use_item.data(Qt.UserRole))
                if index in self.twint_credit_indexes:
                    if index not in self.marked_twint_indexes:
                        mark_only.append(self.transactions[index])
                    continue
                item = super()._build_item(row)
                if item is not None:
                    plan.append(item)
        except ValueError as exc:
            QMessageBox.warning(self, "Import prüfen", str(exc))
            return

        if not plan and not mark_only:
            QMessageBox.information(
                self,
                "Bankimport",
                "Keine neuen Buchungen oder TWINT-Markierungen ausgewählt.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Bankimport bestätigen",
            f"{len(plan)} Budgetbuchungen importieren und "
            f"{len(mark_only)} TWINT-Eingänge nur als bearbeitet markieren?\n\n"
            "TWINT-Eingänge werden ausdrücklich nicht als Einkommen gebucht.",
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

        marked = 0
        try:
            if mark_only:
                marked = self.marker_store.mark_transactions(
                    mark_only,
                    self.document_digest,
                )
        except sqlite3.Error as exc:
            QMessageBox.warning(
                self,
                "TWINT-Markierung unvollständig",
                f"{imported} Budgetbuchungen wurden übernommen, aber die "
                f"TWINT-Markierung konnte nicht vollständig gespeichert werden: {exc}\n\n"
                "Es wurde trotzdem kein TWINT-Eingang als Einkommen gebucht.",
            )
            return

        QMessageBox.information(
            self,
            "Bankimport abgeschlossen",
            f"{imported} Budgetbuchungen importiert; {skipped} Duplikate übersprungen; "
            f"{marked} TWINT-Eingänge nur markiert. "
            "TWINT-Markierungen haben keine Budgetwirkung und werden nicht als Einkommen gebucht.",
        )
        self.accept()


__all__ = ["BankImportDialog"]
