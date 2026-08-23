"""Review-first PDF/CSV-Bankimport mit lokaler Lern-KI."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from model.bank_import_ai import (
    BookingSignal,
    ReimbursementMatch,
    match_twint_reimbursement,
)
from model.bank_import_service import (
    BankImportItem,
    BankImportService,
    source_digest,
)
from model.bank_statement_reader import (
    BankStatementError,
    BankTransaction,
    load_transactions,
)
from model.category_model import CategoryModel
from model.tags_model import TagsModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from utils.money import get_currency


class BankImportDialog(QDialog):
    COL_USE = 0
    COL_DATE = 1
    COL_TYPE = 2
    COL_AMOUNT = 3
    COL_TEXT = 4
    COL_CATEGORY = 5
    COL_TAGS = 6
    COL_AI = 7
    COL_TWINT = 8
    COL_EFFECTIVE = 9

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.categories = CategoryModel(conn)
        self.tags = TagsModel(conn)
        self.service = BankImportService(conn)
        self.ai = self.service.ai
        self.transactions: list[BankTransaction] = []
        self.matches: dict[int, ReimbursementMatch] = {}
        self.matched_credit_indexes: set[int] = set()
        self.duplicate_indexes: set[int] = set()
        self.document_digest = ""

        self.setWindowTitle("Bank PDF/CSV importieren")
        self.resize(1380, 720)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Lokaler Import: Nichts wird ohne Bestätigung gebucht. "
            "Die KI lernt Kategorie und Tags erst aus bestätigten Zeilen. "
            "Bereits importierte Bankbuchungen werden markiert und übersprungen."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        tools = QHBoxLayout()
        self.btn_open = QPushButton("PDF/CSV öffnen…")
        self.lbl_file = QLabel("Keine Datei gewählt")
        self.chk_net_twint = QCheckBox(
            "Erkannte TWINT-Erstattungen als Eigenanteil verrechnen"
        )
        self.chk_net_twint.setChecked(True)
        tools.addWidget(self.btn_open)
        tools.addWidget(self.lbl_file, 1)
        tools.addWidget(self.chk_net_twint)
        root.addLayout(tools)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Import",
                "Datum",
                "Typ",
                "Betrag",
                "Buchungstext",
                "Kategorie",
                "Tags",
                "KI",
                "TWINT / Status",
                "Budgetbetrag",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        for column, width in enumerate((60, 100, 95, 100, 330, 200, 220, 120, 220, 110)):
            self.table.setColumnWidth(column, width)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.btn_import = QPushButton("Bestätigte Zeilen importieren & lernen")
        self.btn_close = QPushButton("Schließen")
        bottom.addWidget(self.lbl_summary, 1)
        bottom.addWidget(self.btn_import)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        self.btn_open.clicked.connect(self.open_file)
        self.chk_net_twint.toggled.connect(self._refresh_effective_view)
        self.btn_import.clicked.connect(self.import_selected)
        self.btn_close.clicked.connect(self.reject)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Kontoauszug wählen",
            "",
            "Kontoauszüge (*.csv *.pdf);;CSV (*.csv);;PDF (*.pdf)",
        )
        if not path:
            return
        try:
            transactions = load_transactions(path, get_currency().upper())
            digest = source_digest(path)
        except (BankStatementError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import nicht möglich", str(exc))
            return

        self.document_digest = digest
        self.transactions = transactions
        self.duplicate_indexes = self.service.duplicate_indexes(transactions, digest)
        self.lbl_file.setText(Path(path).name)
        self._build_matches()
        self._populate()

    @staticmethod
    def _signal(index: int, tx: BankTransaction) -> BookingSignal:
        return BookingSignal(
            booking_id=f"row:{index}",
            booking_date=tx.booking_date,
            amount=float(tx.amount),
            description=tx.description,
            counterparty=tx.counterparty,
        )

    def _build_matches(self) -> None:
        self.matches.clear()
        self.matched_credit_indexes.clear()
        credits = [
            self._signal(index, tx)
            for index, tx in enumerate(self.transactions)
            if tx.amount > 0 and index not in self.duplicate_indexes
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
            if credit_index in self.matched_credit_indexes:
                continue
            self.matches[index] = match
            self.matched_credit_indexes.add(credit_index)

    def _category_combo(self, typ: str, predicted: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("— bitte wählen —", "")
        for name in self.categories.list_names(typ):
            combo.addItem(name, name)
        if predicted:
            index = combo.findData(predicted)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _populate(self) -> None:
        self.table.setRowCount(0)
        for index, tx in enumerate(self.transactions):
            row = self.table.rowCount()
            self.table.insertRow(row)
            typ = TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
            prediction = self.ai.predict(
                typ=typ,
                description=tx.description,
                counterparty=tx.counterparty,
            )

            use_item = QTableWidgetItem()
            use_item.setData(Qt.UserRole, index)
            if index in self.duplicate_indexes:
                use_item.setFlags(Qt.ItemIsEnabled)
                use_item.setCheckState(Qt.Unchecked)
            else:
                use_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                use_item.setCheckState(Qt.Checked)
            self.table.setItem(row, self.COL_USE, use_item)
            self.table.setItem(
                row,
                self.COL_DATE,
                QTableWidgetItem(tx.booking_date.strftime("%d.%m.%Y")),
            )
            self.table.setItem(row, self.COL_TYPE, QTableWidgetItem(typ))
            self.table.setItem(
                row,
                self.COL_AMOUNT,
                QTableWidgetItem(f"{abs(tx.amount):.2f} {tx.currency}"),
            )
            self.table.setItem(row, self.COL_TEXT, QTableWidgetItem(tx.description))
            self.table.setCellWidget(
                row,
                self.COL_CATEGORY,
                self._category_combo(typ, prediction.category),
            )

            tags_edit = QLineEdit(", ".join(prediction.tags))
            tags_edit.setPlaceholderText("vorhandene Tags, mit Komma getrennt")
            tags_edit.textChanged.connect(
                lambda _text: self._refresh_effective_view()
            )
            self.table.setCellWidget(row, self.COL_TAGS, tags_edit)
            confidence = (
                f"{prediction.method} {prediction.confidence * 100:.0f}%"
                if prediction.category
                else prediction.method
            )
            self.table.setItem(row, self.COL_AI, QTableWidgetItem(confidence))
            self.table.setItem(row, self.COL_TWINT, QTableWidgetItem(""))
            self.table.setItem(
                row,
                self.COL_EFFECTIVE,
                QTableWidgetItem(f"{abs(tx.amount):.2f}"),
            )
        self._refresh_effective_view()

    def _raw_tag_names(self, row: int) -> tuple[str, ...]:
        edit = self.table.cellWidget(row, self.COL_TAGS)
        if not isinstance(edit, QLineEdit):
            return ()
        return tuple(
            dict.fromkeys(
                part.strip()
                for part in edit.text().split(",")
                if part.strip()
            )
        )

    def _tag_names(self, row: int) -> tuple[str, ...]:
        names = self._raw_tag_names(row)
        known = {tag.name.casefold(): tag.name for tag in self.tags.list_all()}
        invalid = [name for name in names if name.casefold() not in known]
        if invalid:
            raise ValueError("Unbekannte Tags: " + ", ".join(invalid))
        return tuple(known[name.casefold()] for name in names)

    def _effective_amount(
        self,
        index: int,
        row: int,
        *,
        strict_tags: bool = False,
    ) -> tuple[float, str]:
        tx = self.transactions[index]
        base = abs(float(tx.amount))
        if tx.amount >= 0:
            return base, ""

        match = self.matches.get(index)
        if match and self.chk_net_twint.isChecked():
            return max(0.0, base - match.reimbursement_amount), "twint"

        try:
            tags = self._tag_names(row) if strict_tags else self._raw_tag_names(row)
            if not strict_tags:
                known = {
                    tag.name.casefold(): tag.name for tag in self.tags.list_all()
                }
                tags = tuple(
                    known[name.casefold()]
                    for name in tags
                    if name.casefold() in known
                )
            allocation, source_tag = self.ai.allocation_for_tags(tags)
        except ValueError:
            if strict_tags:
                raise
            allocation, source_tag = None, ""
        if allocation is not None:
            return base * allocation / 100.0, source_tag
        return base, ""

    def _refresh_effective_view(self) -> None:
        net = self.chk_net_twint.isChecked()
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            status = ""
            if index in self.duplicate_indexes:
                status = "bereits importiert"
            else:
                match = self.matches.get(index)
                if match:
                    status = (
                        f"+{match.reimbursement_amount:.2f}; "
                        f"{match.reimbursement_percent:.0f}% erstattet; "
                        f"{match.confidence * 100:.0f}% sicher"
                    )
                if index in self.matched_credit_indexes:
                    if net:
                        use_item.setCheckState(Qt.Unchecked)
                        status = "wird mit zugehöriger Ausgabe verrechnet"
                    else:
                        use_item.setCheckState(Qt.Checked)
            effective, source = self._effective_amount(index, row)
            if source and source != "twint":
                prefix = status + " · " if status else ""
                status = prefix + f"Tag-Regel: {source}"
            self.table.item(row, self.COL_TWINT).setText(status)
            self.table.item(row, self.COL_EFFECTIVE).setText(f"{effective:.2f}")
        self._update_summary()

    def _update_summary(self) -> None:
        selected = sum(
            1
            for row in range(self.table.rowCount())
            if self.table.item(row, self.COL_USE)
            and self.table.item(row, self.COL_USE).checkState() == Qt.Checked
        )
        self.lbl_summary.setText(
            f"{len(self.transactions)} erkannt · {selected} ausgewählt · "
            f"{len(self.matches)} TWINT-Vorschläge · "
            f"{len(self.duplicate_indexes)} bereits importiert"
        )

    def _build_item(self, row: int) -> BankImportItem | None:
        use_item = self.table.item(row, self.COL_USE)
        if use_item is None or use_item.checkState() != Qt.Checked:
            return None
        index = int(use_item.data(Qt.UserRole))
        if index in self.duplicate_indexes:
            return None

        tx = self.transactions[index]
        typ = TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
        combo = self.table.cellWidget(row, self.COL_CATEGORY)
        category = (
            str(combo.currentData() or "") if isinstance(combo, QComboBox) else ""
        )
        if not category:
            raise ValueError(f"Zeile {row + 1}: Bitte eine Kategorie wählen.")
        tag_names = self._tag_names(row)
        amount, allocation_source = self._effective_amount(
            index,
            row,
            strict_tags=True,
        )
        if amount <= 0:
            return None

        details = tx.description
        if tx.counterparty and tx.counterparty.casefold() not in details.casefold():
            details = f"{details} | {tx.counterparty}"
        match = self.matches.get(index)
        if match and self.chk_net_twint.isChecked():
            details += (
                f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                f"TWINT-Erstattung {match.reimbursement_amount:.2f}; "
                f"Eigenanteil {match.personal_share_percent:.2f}%"
            )
        elif allocation_source and allocation_source != "twint":
            allocation, _ = self.ai.allocation_for_tags(tag_names)
            details += (
                f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                f"Tag-Regel {allocation_source} {allocation:.2f}%"
            )
        return BankImportItem(
            transaction=tx,
            typ=typ,
            category=category,
            tags=tag_names,
            amount=amount,
            details=details,
        )

    def import_selected(self) -> None:
        if not self.transactions or not self.document_digest:
            QMessageBox.information(
                self,
                "Bankimport",
                "Bitte zuerst eine PDF- oder CSV-Datei öffnen.",
            )
            return

        plan: list[BankImportItem] = []
        try:
            for row in range(self.table.rowCount()):
                item = self._build_item(row)
                if item is not None:
                    plan.append(item)
        except ValueError as exc:
            QMessageBox.warning(self, "Import prüfen", str(exc))
            return

        if not plan:
            QMessageBox.information(
                self,
                "Bankimport",
                "Keine neuen importierbaren Zeilen ausgewählt.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Bankimport bestätigen",
            f"{len(plan)} Buchungen atomar importieren? "
            "Erst nach dieser Bestätigung lernt die lokale KI.",
        )
        if answer != QMessageBox.Yes:
            return

        try:
            result = self.service.import_items(
                plan,
                document_digest=self.document_digest,
            )
        except (sqlite3.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Bankimport fehlgeschlagen",
                "Es wurde nichts aus diesem Batch übernommen.\n\n" + str(exc),
            )
            return

        QMessageBox.information(
            self,
            "Bankimport abgeschlossen",
            f"{result.imported} Buchungen importiert; "
            f"{result.skipped_duplicates} Duplikate übersprungen. "
            "Bestätigte Kategorien und Tags wurden lokal gelernt.",
        )
        self.accept()
