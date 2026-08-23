"""Review-first PDF/CSV-Bankimport mit lokaler Lern-KI."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from model.bank_import_ai import BankImportAI, BookingSignal, ReimbursementMatch, match_twint_reimbursement
from model.bank_statement_reader import BankStatementError, BankTransaction, load_transactions
from model.category_model import CategoryModel
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
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
        self.tracking = TrackingModel(conn)
        self.categories = CategoryModel(conn)
        self.tags = TagsModel(conn)
        self.ai = BankImportAI(conn)
        self.transactions: list[BankTransaction] = []
        self.matches: dict[int, ReimbursementMatch] = {}
        self.matched_credit_indexes: set[int] = set()
        self.setWindowTitle("Bank PDF/CSV importieren")
        self.resize(1380, 720)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Lokaler Import: Nichts wird ohne Bestätigung gebucht. "
            "Die KI lernt Kategorie und Tags erst aus bestätigten Zeilen."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        tools = QHBoxLayout()
        self.btn_open = QPushButton("PDF/CSV öffnen…")
        self.lbl_file = QLabel("Keine Datei gewählt")
        self.chk_net_twint = QCheckBox("Erkannte TWINT-Erstattungen als Eigenanteil verrechnen")
        self.chk_net_twint.setChecked(True)
        tools.addWidget(self.btn_open)
        tools.addWidget(self.lbl_file, 1)
        tools.addWidget(self.chk_net_twint)
        root.addLayout(tools)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["Import", "Datum", "Typ", "Betrag", "Buchungstext", "Kategorie", "Tags", "KI", "TWINT", "Eigenanteil"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(self.COL_USE, 60)
        self.table.setColumnWidth(self.COL_DATE, 100)
        self.table.setColumnWidth(self.COL_TYPE, 95)
        self.table.setColumnWidth(self.COL_AMOUNT, 100)
        self.table.setColumnWidth(self.COL_TEXT, 330)
        self.table.setColumnWidth(self.COL_CATEGORY, 200)
        self.table.setColumnWidth(self.COL_TAGS, 220)
        self.table.setColumnWidth(self.COL_AI, 120)
        self.table.setColumnWidth(self.COL_TWINT, 180)
        self.table.setColumnWidth(self.COL_EFFECTIVE, 110)
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
        self.chk_net_twint.toggled.connect(self._refresh_twint_view)
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
        except (BankStatementError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import nicht möglich", str(exc))
            return
        self.transactions = transactions
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
        credits = [self._signal(i, tx) for i, tx in enumerate(self.transactions) if tx.amount > 0]
        for i, tx in enumerate(self.transactions):
            if tx.amount >= 0:
                continue
            match = match_twint_reimbursement(self._signal(i, tx), credits)
            if match is None:
                continue
            try:
                credit_index = int(match.credit_id.split(":", 1)[1])
            except (ValueError, IndexError):
                continue
            if credit_index in self.matched_credit_indexes:
                continue
            self.matches[i] = match
            self.matched_credit_indexes.add(credit_index)

    def _category_combo(self, typ: str, predicted: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("— bitte wählen —", "")
        for name in self.categories.list_names(typ):
            combo.addItem(name, name)
        if predicted:
            idx = combo.findData(predicted)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        return combo

    def _populate(self) -> None:
        self.table.setRowCount(0)
        for index, tx in enumerate(self.transactions):
            row = self.table.rowCount()
            self.table.insertRow(row)
            typ = TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
            prediction = self.ai.predict(
                typ=typ, description=tx.description, counterparty=tx.counterparty
            )

            use_item = QTableWidgetItem()
            use_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            use_item.setCheckState(Qt.Checked)
            use_item.setData(Qt.UserRole, index)
            self.table.setItem(row, self.COL_USE, use_item)
            self.table.setItem(row, self.COL_DATE, QTableWidgetItem(tx.booking_date.strftime("%d.%m.%Y")))
            self.table.setItem(row, self.COL_TYPE, QTableWidgetItem(typ))
            self.table.setItem(row, self.COL_AMOUNT, QTableWidgetItem(f"{abs(tx.amount):.2f} {tx.currency}"))
            self.table.setItem(row, self.COL_TEXT, QTableWidgetItem(tx.description))
            self.table.setCellWidget(row, self.COL_CATEGORY, self._category_combo(typ, prediction.category))

            tags_edit = QLineEdit(", ".join(prediction.tags))
            tags_edit.setPlaceholderText("vorhandene Tags, mit Komma getrennt")
            self.table.setCellWidget(row, self.COL_TAGS, tags_edit)
            confidence = f"{prediction.method} {prediction.confidence * 100:.0f}%" if prediction.category else prediction.method
            self.table.setItem(row, self.COL_AI, QTableWidgetItem(confidence))
            self.table.setItem(row, self.COL_TWINT, QTableWidgetItem(""))
            self.table.setItem(row, self.COL_EFFECTIVE, QTableWidgetItem(f"{abs(tx.amount):.2f}"))
        self._refresh_twint_view()

    def _refresh_twint_view(self) -> None:
        net = self.chk_net_twint.isChecked()
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            tx = self.transactions[index]
            twint_text = ""
            effective = abs(tx.amount)
            match = self.matches.get(index)
            if match:
                twint_text = (
                    f"+{match.reimbursement_amount:.2f}; "
                    f"{match.reimbursement_percent:.0f}% erstattet; "
                    f"{match.confidence * 100:.0f}% sicher"
                )
                if net:
                    effective = Decimal(str(max(0.0, abs(float(tx.amount)) - match.reimbursement_amount)))
            if index in self.matched_credit_indexes and net:
                use_item.setCheckState(Qt.Unchecked)
                twint_text = "wird mit zugehöriger Ausgabe verrechnet"
            elif index not in self.matched_credit_indexes:
                # Nicht automatisch wieder anhaken: Nutzerentscheidung respektieren.
                pass
            self.table.item(row, self.COL_TWINT).setText(twint_text)
            self.table.item(row, self.COL_EFFECTIVE).setText(f"{effective:.2f}")
        self._update_summary()

    def _update_summary(self) -> None:
        selected = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_USE)
            if item and item.checkState() == Qt.Checked:
                selected += 1
        self.lbl_summary.setText(
            f"{len(self.transactions)} erkannt · {selected} zum Import ausgewählt · "
            f"{len(self.matches)} mögliche TWINT-Erstattungen"
        )

    def _tag_names(self, row: int) -> tuple[str, ...]:
        edit = self.table.cellWidget(row, self.COL_TAGS)
        if not isinstance(edit, QLineEdit):
            return ()
        names = tuple(dict.fromkeys(part.strip() for part in edit.text().split(",") if part.strip()))
        known = {tag.name.casefold(): tag.name for tag in self.tags.list_all()}
        invalid = [name for name in names if name.casefold() not in known]
        if invalid:
            raise ValueError("Unbekannte Tags: " + ", ".join(invalid))
        return tuple(known[name.casefold()] for name in names)

    def import_selected(self) -> None:
        if not self.transactions:
            QMessageBox.information(self, "Bankimport", "Bitte zuerst eine PDF- oder CSV-Datei öffnen.")
            return
        plan: list[tuple[int, BankTransaction, str, str, tuple[str, ...], float]] = []
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None or use_item.checkState() != Qt.Checked:
                continue
            index = int(use_item.data(Qt.UserRole))
            tx = self.transactions[index]
            typ = TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
            combo = self.table.cellWidget(row, self.COL_CATEGORY)
            category = str(combo.currentData() or "") if isinstance(combo, QComboBox) else ""
            if not category:
                QMessageBox.warning(self, "Kategorie fehlt", f"Zeile {row + 1}: Bitte eine Kategorie wählen.")
                return
            try:
                tags = self._tag_names(row)
            except ValueError as exc:
                QMessageBox.warning(self, "Tag unbekannt", f"Zeile {row + 1}: {exc}")
                return
            amount = abs(float(tx.amount))
            match = self.matches.get(index)
            if match and self.chk_net_twint.isChecked():
                amount = max(0.0, amount - match.reimbursement_amount)
            if amount <= 0:
                continue
            plan.append((row, tx, typ, category, tags, amount))

        if not plan:
            QMessageBox.information(self, "Bankimport", "Keine importierbaren Zeilen ausgewählt.")
            return

        answer = QMessageBox.question(
            self,
            "Bankimport bestätigen",
            f"{len(plan)} Buchungen importieren? Erst nach dieser Bestätigung lernt die lokale KI.",
        )
        if answer != QMessageBox.Yes:
            return

        imported = 0
        try:
            for row, tx, typ, category, tag_names, amount in plan:
                details = tx.description
                if tx.counterparty and tx.counterparty.casefold() not in details.casefold():
                    details = f"{details} | {tx.counterparty}"
                match = self.matches.get(int(self.table.item(row, self.COL_USE).data(Qt.UserRole)))
                if match and self.chk_net_twint.isChecked():
                    details += (
                        f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                        f"TWINT-Erstattung {match.reimbursement_amount:.2f}; "
                        f"Eigenanteil {match.personal_share_percent:.2f}%"
                    )
                entry_id = self.tracking.add(
                    tx.booking_date, typ, category, amount, details, source="bank_import"
                )
                if tag_names:
                    by_name = {tag.name.casefold(): tag.id for tag in self.tags.list_all()}
                    self.tags.set_entry_tags(entry_id, [by_name[name.casefold()] for name in tag_names])
                self.ai.learn(
                    typ=typ,
                    category=category,
                    description=tx.description,
                    counterparty=tx.counterparty,
                    tags=tag_names,
                )
                imported += 1
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Bankimport fehlgeschlagen",
                f"Import wurde nach {imported} Buchungen abgebrochen: {exc}",
            )
            return

        QMessageBox.information(
            self,
            "Bankimport abgeschlossen",
            f"{imported} Buchungen importiert. Bestätigte Kategorien und Tags wurden lokal gelernt.",
        )
        self.accept()
