from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QDateEdit, QVBoxLayout, QMessageBox
)

from model.category_model import CategoryModel

def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF","").strip()
    s = s.replace("'", "").replace(" ", "").replace(",", ".")
    return float(s)

@dataclass(frozen=True)
class TrackingInput:
    d: date
    typ: str
    category: str
    amount: float
    details: str

class TrackerDialog(QDialog):
    def __init__(self, parent=None, *, conn: sqlite3.Connection, cats: CategoryModel, preset: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Tracking Eintrag")
        self.setModal(True)
        self.cats = cats

        self.ed_date = QDateEdit()
        self.ed_date.setCalendarPopup(True)
        self.ed_date.setDate(date.today())

        self.cb_typ = QComboBox()
        self.cb_typ.addItems(["Ausgaben","Einkommen","Ersparnisse"])

        self.cb_cat = QComboBox()
        self.cb_cat.setEnabled(False)

        self.ed_amount = QLineEdit()
        self.ed_amount.setPlaceholderText("z.B. 12.50")

        self.ed_details = QLineEdit()

        self.btn_ok = QPushButton("Speichern")
        self.btn_cancel = QPushButton("Abbrechen")

        form = QFormLayout()
        form.addRow("Datum", self.ed_date)
        form.addRow("Typ", self.cb_typ)
        form.addRow("Kategorie", self.cb_cat)
        form.addRow("CHF", self.ed_amount)
        form.addRow("Details", self.ed_details)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        self.cb_typ.currentTextChanged.connect(self._fill_categories)
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._fill_categories(self.cb_typ.currentText())

        if preset:
            self._apply_preset(preset)

    def _apply_preset(self, p: dict) -> None:
        # date: "dd.mm.yyyy" or iso
        if "date" in p and p["date"]:
            s = str(p["date"]).strip()
            try:
                if "." in s:
                    d = datetime.strptime(s, "%d.%m.%Y").date()
                else:
                    d = date.fromisoformat(s)
                self.ed_date.setDate(d)
            except Exception:
                pass
        if "typ" in p and p["typ"]:
            self.cb_typ.setCurrentText(str(p["typ"]))
        self._fill_categories(self.cb_typ.currentText())
        if "category" in p and p["category"]:
            self.cb_cat.setCurrentText(str(p["category"]))
        if "amount" in p and p["amount"] is not None:
            self.ed_amount.setText(str(p["amount"]))
        if "details" in p and p["details"] is not None:
            self.ed_details.setText(str(p["details"]))

    def _fill_categories(self, typ: str) -> None:
        self.cb_cat.setEnabled(True)
        self.cb_cat.clear()
        self.cb_cat.addItems(self.cats.list_names(typ))

    def _validate_and_accept(self) -> None:
        if not self.cb_typ.currentText():
            QMessageBox.warning(self, "Fehlt", "Bitte Typ auswählen.")
            return
        if not self.cb_cat.currentText():
            QMessageBox.warning(self, "Fehlt", "Bitte Kategorie auswählen.")
            return
        try:
            amt = parse_amount(self.ed_amount.text())
        except Exception:
            QMessageBox.warning(self, "Fehler", "Betrag ist ungültig.")
            return
        if self.cb_typ.currentText() == "Ausgaben" and amt < 0:
            QMessageBox.warning(self, "Nicht erlaubt", "Bei Ausgaben sind negative Beträge nicht erlaubt.")
            return
        self.accept()

    def get_input(self) -> TrackingInput:
        d = self.ed_date.date().toPython()
        typ = self.cb_typ.currentText()
        cat = self.cb_cat.currentText()
        amt = parse_amount(self.ed_amount.text())
        details = self.ed_details.text() or ""
        return TrackingInput(d, typ, cat, float(amt), details)
