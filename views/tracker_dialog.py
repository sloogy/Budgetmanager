from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from dataclasses import dataclass
from datetime import date, datetime
import sqlite3

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QDateEdit, QVBoxLayout, QMessageBox
)

from model.category_model import CategoryModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS, normalize_typ
from utils.money import parse_money, currency_header
from utils.i18n import tr, trf, display_typ, db_typ_from_display

def parse_amount(text: str) -> float:
    return parse_money(text)

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
        self.setMinimumSize(650, 420)
        self.setWindowTitle(tr("dlg.tracking_entry"))
        self.setModal(True)
        self.conn = conn
        self.cats = cats
        self._track = TrackingModel(conn)

        self.ed_date = QDateEdit()
        self.ed_date.setCalendarPopup(True)
        self.ed_date.setDate(date.today())

        self.cb_typ = QComboBox()
        self.cb_typ.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.cb_typ.addItem(tr("kpi.income"), TYP_INCOME)
        self.cb_typ.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)

        self.cb_cat = QComboBox()
        self.cb_cat.setEnabled(False)

        self.ed_amount = QLineEdit()
        self.ed_amount.setPlaceholderText("z.B. 12.50")

        self.ed_details = QLineEdit()

        self.btn_ok = QPushButton(tr("btn.save"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        form = QFormLayout()
        form.addRow("Datum", self.ed_date)
        form.addRow("Typ", self.cb_typ)
        form.addRow(tr("header.category"), self.cb_cat)
        form.addRow(currency_header(), self.ed_amount)
        form.addRow("Details", self.ed_details)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        self.cb_typ.currentIndexChanged.connect(lambda _: self._fill_categories())
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._fill_categories()

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
            except Exception as e:
                logger.debug("if '.' in s:: %s", e)
        if "typ" in p and p["typ"]:
            raw_typ = str(p["typ"]).strip()
            typ_db = normalize_typ(db_typ_from_display(raw_typ))
            self._set_combo_by_data(self.cb_typ, typ_db)
        self._fill_categories()
        if "category" in p and p["category"]:
            self._set_combo_by_data(self.cb_cat, str(p["category"]))
        if "amount" in p and p["amount"] is not None:
            self.ed_amount.setText(str(p["amount"]))
        if "details" in p and p["details"] is not None:
            self.ed_details.setText(str(p["details"]))


    def _set_combo_by_data(self, combo, value: str) -> None:
        """Setzt ComboBox-Auswahl über itemData (fallback: Textvergleich)."""
        if not value:
            return
        value = str(value)
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data == value:
                combo.setCurrentIndex(i)
                return
        # Fallback: Text ohne Einrückung
        for i in range(combo.count()):
            if str(combo.itemText(i)).strip() == value:
                combo.setCurrentIndex(i)
                return

    def _fill_categories(self) -> None:
        typ = self.cb_typ.currentData() or db_typ_from_display(self.cb_typ.currentText())
        self.cb_cat.setEnabled(True)
        self.cb_cat.clear()

        # Häufigkeit abfragen: wie oft wurde jede Kategorie dieses Typs gebucht?
        freq: dict[str, int] = {}
        try:
            freq = self._track.category_usage_counts(typ)
        except Exception as e:
            logger.debug("category_usage_counts: %s", e)

        # Kategorien laden (flach oder tree)
        pairs: list[tuple[str, str]] = []
        if hasattr(self.cats, "list_names_tree"):
            try:
                pairs = self.cats.list_names_tree(typ)
            except Exception:
                pairs = []
        if not pairs:
            pairs = [(n, n) for n in self.cats.list_names(typ)]

        # Sortierung: Häufigkeit absteigend, dann alphabetisch
        # Tree-Einrückung entfernen für saubere Frequenz-Sortierung
        pairs.sort(key=lambda p: (-freq.get(p[1], 0), p[1].lower()))

        for label, real in pairs:
            # Einrückung entfernen (Frequenz-Sortierung macht Tree-Struktur sinnlos)
            display = label.strip()
            self.cb_cat.addItem(display, real)

    def _validate_and_accept(self) -> None:
        typ = self.cb_typ.currentData() or db_typ_from_display(self.cb_typ.currentText())
        if not typ:
            QMessageBox.warning(self, "Fehlt", tr("dlg.bitte_typ_auswaehlen"))
            return
        if not self.cb_cat.currentText():
            QMessageBox.warning(self, "Fehlt", tr("dlg.bitte_kategorie_auswaehlen"))
            return
        try:
            amt = parse_amount(self.ed_amount.text())
        except Exception:
            QMessageBox.warning(self, "Hinweis", tr("dlg.betrag_ist_ungueltig"))
            return
        if typ == TYP_EXPENSES and amt < 0:
            QMessageBox.warning(self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative"))
            return
        self.accept()

    def get_input(self) -> TrackingInput:
        d = self.ed_date.date().toPython()
        typ = self.cb_typ.currentData() or db_typ_from_display(self.cb_typ.currentText())
        cat = self.cb_cat.currentData() or self.cb_cat.currentText().strip()
        amt = parse_amount(self.ed_amount.text())
        details = self.ed_details.text() or ""
        return TrackingInput(d, typ, cat, float(amt), details)
