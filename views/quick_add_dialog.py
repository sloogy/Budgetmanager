from __future__ import annotations
import sqlite3
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QDateEdit, QPushButton,
    QDialogButtonBox, QCompleter, QMessageBox
)

from model.category_model import CategoryModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS, normalize_typ
from utils.money import currency_header


import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display
logger = logging.getLogger(__name__)

class QuickAddDialog(QDialog):
    """Schnelleingabe-Dialog für neue Tracking-Einträge (Strg+N)"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.cats = CategoryModel(conn)
        self.tracking = TrackingModel(conn)
        
        self.setWindowTitle(tr("dlg.quick_add"))
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Info
        info = QLabel(tr("lbl.lbl_quick_add_title"))
        layout.addWidget(info)
        
        # Datum (heute als Standard)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel(tr("lbl.lbl_date")))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(date.today())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        date_row.addWidget(self.date_edit, 1)
        layout.addLayout(date_row)
        
        # Typ
        typ_row = QHBoxLayout()
        typ_row.addWidget(QLabel("Typ:"))
        self.typ_combo = QComboBox()
        self.typ_combo.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ_combo.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        self.typ_combo.currentIndexChanged.connect(lambda _: self._update_categories())
        typ_row.addWidget(self.typ_combo, 1)
        layout.addLayout(typ_row)
        
        # Kategorie mit Autocomplete
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel(tr("lbl.category")))
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self._update_categories()
        cat_row.addWidget(self.cat_combo, 1)
        layout.addLayout(cat_row)
        
        # Betrag
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel(tr("lbl.lbl_amount")))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setPrefix(f"{currency_header()} ")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(10)
        amount_row.addWidget(self.amount_spin, 1)
        layout.addLayout(amount_row)
        
        # Details
        details_row = QHBoxLayout()
        details_row.addWidget(QLabel(tr("lbl.lbl_details")))
        self.details_edit = QLineEdit()
        self.details_edit.setPlaceholderText("Optional: Beschreibung...")
        details_row.addWidget(self.details_edit, 1)
        layout.addLayout(details_row)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save_add = QPushButton(tr("btn.btn_save_and_new"))
        self.btn_save_add.clicked.connect(self._save_and_new)
        btn_layout.addWidget(self.btn_save_add)
        
        self.btn_save_close = QPushButton(tr("btn.speichern_schliessen_1"))
        self.btn_save_close.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.btn_save_close)
        
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Enter = Speichern & Schließen
        self.amount_spin.setFocus()
    
    def _update_categories(self):
        """Aktualisiert die Kategorien basierend auf dem Typ – sortiert nach Häufigkeit."""
        typ = self.typ_combo.currentData() or db_typ_from_display(self.typ_combo.currentText())

        current_data = self.cat_combo.currentData() or self.cat_combo.currentText().strip()
        self.cat_combo.clear()

        # Häufigkeit abfragen
        freq = self.tracking.category_usage_counts(typ)

        pairs: list[tuple[str, str]] = []
        if hasattr(self.cats, "list_names_tree"):
            try:
                pairs = self.cats.list_names_tree(typ)
            except Exception:
                pairs = []
        if not pairs:
            pairs = [(n, n) for n in self.cats.list_names(typ)]

        # Sortierung: Häufigkeit absteigend, dann alphabetisch
        pairs.sort(key=lambda p: (-freq.get(p[1], 0), p[1].lower()))

        for label, real in pairs:
            self.cat_combo.addItem(label.strip(), real)

        # Vorherige Auswahl wiederherstellen
        if current_data:
            for i in range(self.cat_combo.count()):
                if self.cat_combo.itemData(i) == current_data or self.cat_combo.itemText(i).strip() == current_data:
                    self.cat_combo.setCurrentIndex(i)
                    break
    
    def _validate(self) -> bool:
        """Prüft ob alle Pflichtfelder ausgefüllt sind"""
        if not self.cat_combo.currentText().strip():
            QMessageBox.warning(self, "Hinweis", tr("dlg.bitte_eine_kategorie_auswaehlen"))
            return False
        
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Hinweis", tr("dlg.bitte_einen_betrag_0"))
            return False
        
        return True
    
    def _save_entry(self) -> bool:
        """Speichert den Eintrag"""
        if not self._validate():
            return False
        
        d = self.date_edit.date().toPython()
        typ = self.typ_combo.currentData() or db_typ_from_display(self.typ_combo.currentText())
        typ = normalize_typ(typ)
        category = (self.cat_combo.currentData() or self.cat_combo.currentText()).strip()
        amount = self.amount_spin.value()
        details = self.details_edit.text().strip()
        
        # Auto-Details generieren wenn leer
        if not details:
            month_names = [tr(f"month.{i}") for i in range(1, 13)]
            details = f"{month_names[d.month - 1]} - {category}"
        
        self.tracking.add(d, typ, category, amount, details)
        return True
    
    def _save_and_new(self):
        """Speichern und Dialog für neuen Eintrag vorbereiten"""
        if self._save_entry():
            # Felder zurücksetzen für nächsten Eintrag
            self.amount_spin.setValue(0)
            self.details_edit.clear()
            self.amount_spin.setFocus()
            self.amount_spin.selectAll()
    
    def _save_and_close(self):
        """Speichern und Dialog schließen"""
        if self._save_entry():
            self.accept()
