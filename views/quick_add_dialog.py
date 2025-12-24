from __future__ import annotations
import sqlite3
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QDateEdit, QPushButton,
    QDialogButtonBox, QCompleter, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from model.category_model import CategoryModel
from model.tracking_model import TrackingModel


class QuickAddDialog(QDialog):
    """Schnelleingabe-Dialog für neue Tracking-Einträge (Strg+N)"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.cats = CategoryModel(conn)
        self.tracking = TrackingModel(conn)
        
        self.setWindowTitle("⚡ Schnelleingabe")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Info
        info = QLabel("Schnell einen neuen Eintrag erfassen:")
        layout.addWidget(info)
        
        # Datum (heute als Standard)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Datum:"))
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
        self.typ_combo.addItems(["Ausgaben", "Einkommen", "Ersparnisse"])
        self.typ_combo.currentTextChanged.connect(self._update_categories)
        typ_row.addWidget(self.typ_combo, 1)
        layout.addLayout(typ_row)
        
        # Kategorie mit Autocomplete
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Kategorie:"))
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self._update_categories()
        cat_row.addWidget(self.cat_combo, 1)
        layout.addLayout(cat_row)
        
        # Betrag
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel("Betrag:"))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setPrefix("CHF ")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(10)
        amount_row.addWidget(self.amount_spin, 1)
        layout.addLayout(amount_row)
        
        # Details
        details_row = QHBoxLayout()
        details_row.addWidget(QLabel("Details:"))
        self.details_edit = QLineEdit()
        self.details_edit.setPlaceholderText("Optional: Beschreibung...")
        details_row.addWidget(self.details_edit, 1)
        layout.addLayout(details_row)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_save_add = QPushButton("💾 Speichern && Neu")
        self.btn_save_add.clicked.connect(self._save_and_new)
        btn_layout.addWidget(self.btn_save_add)
        
        self.btn_save_close = QPushButton("✅ Speichern && Schließen")
        self.btn_save_close.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.btn_save_close)
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Enter = Speichern & Schließen
        self.amount_spin.setFocus()
    
    def _update_categories(self):
        """Aktualisiert die Kategorien basierend auf dem Typ"""
        typ = self.typ_combo.currentText()
        cats = self.cats.list_names(typ)
        
        current = self.cat_combo.currentText()
        self.cat_combo.clear()
        self.cat_combo.addItems(cats)
        
        # Versuche vorherige Auswahl wiederherzustellen
        idx = self.cat_combo.findText(current)
        if idx >= 0:
            self.cat_combo.setCurrentIndex(idx)
    
    def _validate(self) -> bool:
        """Prüft ob alle Pflichtfelder ausgefüllt sind"""
        if not self.cat_combo.currentText().strip():
            QMessageBox.warning(self, "Fehler", "Bitte eine Kategorie auswählen.")
            return False
        
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Fehler", "Bitte einen Betrag > 0 eingeben.")
            return False
        
        return True
    
    def _save_entry(self) -> bool:
        """Speichert den Eintrag"""
        if not self._validate():
            return False
        
        d = self.date_edit.date().toPython()
        typ = self.typ_combo.currentText()
        category = self.cat_combo.currentText().strip()
        amount = self.amount_spin.value()
        details = self.details_edit.text().strip()
        
        # Auto-Details generieren wenn leer
        if not details:
            month_names = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                          "Juli", "August", "September", "Oktober", "November", "Dezember"]
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
