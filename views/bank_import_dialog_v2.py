"""Review-first Bankimport V2 mit reaktivem Typ-/Kategorie-Mapping.

Der Dialog unterstützt normale Bank-PDF/CSV-Dateien sowie das strukturierte
Kreditkarten-CSV. Typ, Kategorie und Tags bleiben vor dem Import vollständig
prüf- und korrigierbar.
"""

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
from model.credit_card_statement_reader import (
    is_credit_card_csv,
    load_credit_card_csv,
)
from model.tags_model import TagsModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from utils.i18n import tr
from utils.money import get_currency
from utils.notifications import show_info, show_warning


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
        self.source_format = ""
        self._updating_row = False

        self.setWindowTitle(tr("bank_import.window_title"))
        self.resize(1450, 740)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Lokaler Review-Import: Typ, Kategorie und Tags können pro Zeile "
            "geändert werden. Die Kategorieauswahl folgt sofort dem gewählten "
            "Typ. Die KI lernt erst aus bestätigten Buchungen."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        tools = QHBoxLayout()
        self.btn_open = QPushButton(tr("bank_import.open_file"))
        self.lbl_file = QLabel(tr("bank_import.no_file"))
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
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for column, width in enumerate(
            (60, 100, 130, 105, 360, 220, 220, 135, 220, 110)
        ):
            self.table.setColumnWidth(column, width)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.btn_import = QPushButton(tr("bank_import.import_confirmed"))
        self.btn_close = QPushButton(tr("bank_import.close"))
        bottom.addWidget(self.lbl_summary, 1)
        bottom.addWidget(self.btn_import)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        self.btn_open.clicked.connect(self.open_file)
        self.chk_net_twint.toggled.connect(self._refresh_effective_view)
        self.btn_import.clicked.connect(self.import_selected)
        self.btn_close.clicked.connect(self.reject)

    @staticmethod
    def _default_type(tx: BankTransaction) -> str:
        return TYP_INCOME if tx.amount > 0 else TYP_EXPENSES

    @staticmethod
    def _signal(index: int, tx: BankTransaction) -> BookingSignal:
        return BookingSignal(
            booking_id=f"row:{index}",
            booking_date=tx.booking_date,
            amount=float(tx.amount),
            description=tx.description,
            counterparty=tx.counterparty,
        )

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
            if is_credit_card_csv(path):
                transactions = load_credit_card_csv(path, get_currency().upper())
                source_format = "Kreditkarten-CSV"
            else:
                transactions = load_transactions(path, get_currency().upper())
                source_format = "Bank-CSV/PDF"
            digest = source_digest(path)
        except (BankStatementError, OSError, ValueError) as exc:
            show_warning(self, "Import nicht möglich", str(exc))
            return

        self.document_digest = digest
        self.transactions = transactions
        self.source_format = source_format
        self.duplicate_indexes = self.service.duplicate_indexes(transactions, digest)
        self.lbl_file.setText(f"{Path(path).name} · {source_format}")
        self._build_matches()
        self._populate()

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

    def _type_combo(self, typ: str, row: int) -> QComboBox:
        combo = QComboBox()
        combo.addItem(TYP_EXPENSES, TYP_EXPENSES)
        combo.addItem(TYP_INCOME, TYP_INCOME)
        index = combo.findData(typ)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(
            lambda _index, current_row=row: self._type_changed(current_row)
        )
        return combo

    def _category_combo(self, typ: str, predicted: str = "") -> QComboBox:
        combo = QComboBox()
        combo.addItem(tr("bank_import.choose_placeholder"), "")
        for name in self.categories.list_names(typ):
            combo.addItem(name, name)
        if predicted:
            index = combo.findData(predicted)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _row_type(self, row: int) -> str:
        combo = self.table.cellWidget(row, self.COL_TYPE)
        if isinstance(combo, QComboBox):
            value = str(combo.currentData() or "")
            if value in {TYP_EXPENSES, TYP_INCOME}:
                return value
        use_item = self.table.item(row, self.COL_USE)
        if use_item is None:
            return TYP_EXPENSES
        index = int(use_item.data(Qt.UserRole))
        return self._default_type(self.transactions[index])

    def _set_prediction_for_row(self, row: int, *, replace_tags: bool) -> None:
        use_item = self.table.item(row, self.COL_USE)
        if use_item is None:
            return
        index = int(use_item.data(Qt.UserRole))
        tx = self.transactions[index]
        typ = self._row_type(row)
        prediction = self.ai.predict(
            typ=typ,
            description=tx.description,
            counterparty=tx.counterparty,
        )

        category_combo = self._category_combo(typ, prediction.category)
        self.table.setCellWidget(row, self.COL_CATEGORY, category_combo)

        tags_edit = self.table.cellWidget(row, self.COL_TAGS)
        if replace_tags and isinstance(tags_edit, QLineEdit):
            tags_edit.setText(", ".join(prediction.tags))

        confidence = (
            f"{prediction.method} {prediction.confidence * 100:.0f}%"
            if prediction.category
            else prediction.method
        )
        ai_item = self.table.item(row, self.COL_AI)
        if ai_item is None:
            self.table.setItem(row, self.COL_AI, QTableWidgetItem(confidence))
        else:
            ai_item.setText(confidence)

    def _type_changed(self, row: int) -> None:
        if self._updating_row:
            return
        self._updating_row = True
        try:
            self._set_prediction_for_row(row, replace_tags=True)
            self._refresh_effective_view()
        finally:
            self._updating_row = False

    def _populate(self) -> None:
        self._updating_row = True
        try:
            self.table.setRowCount(0)
            for index, tx in enumerate(self.transactions):
                row = self.table.rowCount()
                self.table.insertRow(row)

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
                self.table.setCellWidget(
                    row,
                    self.COL_TYPE,
                    self._type_combo(self._default_type(tx), row),
                )
                self.table.setItem(
                    row,
                    self.COL_AMOUNT,
                    QTableWidgetItem(f"{abs(tx.amount):.2f} {tx.currency}"),
                )
                self.table.setItem(row, self.COL_TEXT, QTableWidgetItem(tx.description))

                tags_edit = QLineEdit()
                tags_edit.setPlaceholderText(tr("bank_import.tags_free_placeholder"))
                tags_edit.textChanged.connect(
                    lambda _text: self._refresh_effective_view()
                )
                self.table.setCellWidget(row, self.COL_TAGS, tags_edit)
                self.table.setItem(row, self.COL_AI, QTableWidgetItem(""))
                self.table.setItem(row, self.COL_TWINT, QTableWidgetItem(""))
                self.table.setItem(
                    row,
                    self.COL_EFFECTIVE,
                    QTableWidgetItem(f"{abs(tx.amount):.2f}"),
                )
                self._set_prediction_for_row(row, replace_tags=True)
        finally:
            self._updating_row = False
        self._refresh_effective_view()

    def _raw_tag_names(self, row: int) -> tuple[str, ...]:
        edit = self.table.cellWidget(row, self.COL_TAGS)
        if not isinstance(edit, QLineEdit):
            return ()
        return tuple(
            dict.fromkeys(
                part.strip() for part in edit.text().split(",") if part.strip()
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
        typ = self._row_type(row)
        if typ == TYP_INCOME:
            return base, ""

        match = self.matches.get(index)
        if match and self.chk_net_twint.isChecked():
            return max(0.0, base - match.reimbursement_amount), "twint"

        try:
            tags = self._tag_names(row) if strict_tags else self._raw_tag_names(row)
            if not strict_tags:
                known = {tag.name.casefold(): tag.name for tag in self.tags.list_all()}
                tags = tuple(
                    known[name.casefold()] for name in tags if name.casefold() in known
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
        if self._updating_row:
            return
        net = self.chk_net_twint.isChecked()
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.UserRole))
            typ = self._row_type(row)
            status = ""
            if index in self.duplicate_indexes:
                status = "bereits importiert"
            elif typ == TYP_EXPENSES:
                match = self.matches.get(index)
                if match:
                    status = (
                        f"+{match.reimbursement_amount:.2f}; "
                        f"{match.reimbursement_percent:.0f}% erstattet; "
                        f"{match.confidence * 100:.0f}% sicher"
                    )
                if index in self.matched_credit_indexes and net:
                    use_item.setCheckState(Qt.Unchecked)
                    status = "wird mit zugehöriger Ausgabe verrechnet"
            effective, source = self._effective_amount(index, row)
            if source and source != "twint":
                status = (status + " · " if status else "") + f"Tag-Regel: {source}"
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
        format_text = f" · {self.source_format}" if self.source_format else ""
        self.lbl_summary.setText(
            f"{len(self.transactions)} erkannt · {selected} ausgewählt · "
            f"{len(self.matches)} TWINT-Vorschläge · "
            f"{len(self.duplicate_indexes)} bereits importiert{format_text}"
        )

    def _build_item(self, row: int) -> BankImportItem | None:
        use_item = self.table.item(row, self.COL_USE)
        if use_item is None or use_item.checkState() != Qt.Checked:
            return None
        index = int(use_item.data(Qt.UserRole))
        if index in self.duplicate_indexes:
            return None

        tx = self.transactions[index]
        typ = self._row_type(row)
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
        if tx.source_kind == "credit_card_csv":
            original_amount = str(tx.raw.get("OriginalAmount", "") or "").strip()
            original_currency = str(tx.raw.get("OriginalCurrency", "") or "").strip()
            transaction_id = str(tx.raw.get("TransactionId", "") or "").strip()
            if original_amount or original_currency:
                details += f" | Original {original_amount} {original_currency}".rstrip()
            if transaction_id:
                details += f" | Karten-ID {transaction_id}"

        match = self.matches.get(index)
        if typ == TYP_EXPENSES and match and self.chk_net_twint.isChecked():
            details += (
                f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                f"TWINT-Erstattung {match.reimbursement_amount:.2f}; "
                f"Eigenanteil {match.personal_share_percent:.2f}%"
            )
        elif typ == TYP_EXPENSES and allocation_source and allocation_source != "twint":
            allocation, _ = self.ai.allocation_for_tags(tag_names)
            if allocation is not None:
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
            show_info(
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
            show_warning(self, "Import prüfen", str(exc))
            return

        if not plan:
            show_info(
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

        show_info(
            self,
            "Bankimport abgeschlossen",
            f"{result.imported} Buchungen importiert; "
            f"{result.skipped_duplicates} Duplikate übersprungen. "
            "Bestätigte Typen, Kategorien und Tags wurden lokal gelernt.",
        )
        self.accept()
