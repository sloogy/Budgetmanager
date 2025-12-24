from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QMessageBox
)

MONTHS = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF","").strip()
    s = s.replace("'", "").replace(" ", "").replace(",", ".")
    return float(s)

@dataclass(frozen=True)
class BudgetEntryRequest:
    year: int
    typ: str
    category: str
    amount: float
    mode: str              # "Monat", "Alle", "Bereich"
    month: int             # 1..12 (für Mode Monat)
    from_month: int        # 1..12 (für Bereich)
    to_month: int          # 1..12 (für Bereich)
    only_if_empty: bool

class BudgetEntryDialog(QDialog):
    def __init__(self, parent=None, *, default_year: int, default_typ: str, categories: list[str], preset: Optional[dict]=None):
        super().__init__(parent)
        self.setWindowTitle("Budget erfassen / bearbeiten")
        self.setModal(True)

        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(default_year)

        self.typ = QComboBox()
        self.typ.addItems(["Ausgaben","Einkommen","Ersparnisse"])
        self.typ.setCurrentText(default_typ)

        self.category = QComboBox()
        self.category.setEditable(True)
        self._set_categories(categories)

        self.amount = QLineEdit()
        self.amount.setPlaceholderText("z.B. 1200.00")

        self.mode = QComboBox()
        self.mode.addItems(["Monat", "Alle", "Bereich"])

        self.month = QComboBox()
        self.month.addItems(MONTHS)

        self.from_month = QComboBox()
        self.from_month.addItems(MONTHS)

        self.to_month = QComboBox()
        self.to_month.addItems(MONTHS)

        self.only_if_empty = QCheckBox("Nur überschreiben, wenn Zelle leer ist")
        self.only_if_empty.setChecked(False)

        self.btn_ok = QPushButton("Übernehmen")
        self.btn_cancel = QPushButton("Abbrechen")

        form = QFormLayout()
        form.addRow("Jahr", self.year)
        form.addRow("Typ", self.typ)
        form.addRow("Kategorie", self.category)
        form.addRow("Betrag (CHF)", self.amount)
        form.addRow("Modus", self.mode)
        form.addRow("Monat", self.month)
        form.addRow("Von", self.from_month)
        form.addRow("Bis", self.to_month)
        form.addRow("", self.only_if_empty)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        self.mode.currentTextChanged.connect(self._mode_changed)
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._mode_changed(self.mode.currentText())

        if preset:
            self._apply_preset(preset)

    def _set_categories(self, cats: list[str]) -> None:
        self.category.clear()
        self.category.addItems(cats)

    def _apply_preset(self, preset: dict) -> None:
        if "category" in preset and preset["category"]:
            self.category.setCurrentText(str(preset["category"]))
        if "amount" in preset and preset["amount"] is not None:
            self.amount.setText(str(preset["amount"]))
        if "month" in preset and preset["month"]:
            self.month.setCurrentIndex(int(preset["month"]) - 1)
        if "mode" in preset and preset["mode"]:
            self.mode.setCurrentText(str(preset["mode"]))
        if "from_month" in preset and preset["from_month"]:
            self.from_month.setCurrentIndex(int(preset["from_month"]) - 1)
        if "to_month" in preset and preset["to_month"]:
            self.to_month.setCurrentIndex(int(preset["to_month"]) - 1)
        if "only_if_empty" in preset:
            self.only_if_empty.setChecked(bool(preset["only_if_empty"]))

    def _mode_changed(self, mode: str) -> None:
        is_month = mode == "Monat"
        is_range = mode == "Bereich"
        self.month.setEnabled(is_month)
        self.from_month.setEnabled(is_range)
        self.to_month.setEnabled(is_range)

    def _validate_and_accept(self) -> None:
        cat = (self.category.currentText() or "").strip()
        if not cat:
            QMessageBox.warning(self, "Fehlt", "Bitte Kategorie auswählen/eingeben.")
            return
        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, "Fehler", "Betrag ist ungültig.")
            return

        # Ausgaben: negative Zahlen verhindern
        if self.typ.currentText() == "Ausgaben" and amt < 0:
            QMessageBox.warning(self, "Nicht erlaubt", "Bei Ausgaben sind negative Beträge nicht erlaubt.")
            return

        self.accept()

    def get_request(self) -> BudgetEntryRequest:
        mode = self.mode.currentText()
        month = self.month.currentIndex() + 1
        fm = self.from_month.currentIndex() + 1
        tm = self.to_month.currentIndex() + 1
        amt = parse_amount(self.amount.text())

        return BudgetEntryRequest(
            year=int(self.year.value()),
            typ=str(self.typ.currentText()),
            category=str((self.category.currentText() or "").strip()),
            amount=float(amt),
            mode=str(mode),
            month=int(month),
            from_month=int(fm),
            to_month=int(tm),
            only_if_empty=bool(self.only_if_empty.isChecked()),
        )
