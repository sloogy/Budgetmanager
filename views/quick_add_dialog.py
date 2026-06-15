from __future__ import annotations
import sqlite3
from datetime import date
from PySide6.QtCore import Qt
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
        typ_row.addWidget(QLabel(tr('lbl.type')))
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
        self.cat_combo.setInsertPolicy(QComboBox.NoInsert)
        self.cat_combo.setMaxVisibleItems(18)
        self.cat_combo.setToolTip(tr("tracking.category_tip"))
        try:
            self.cat_combo.lineEdit().setPlaceholderText(tr("tracking.category_placeholder"))
        except Exception:
            pass
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
        self.details_edit.setPlaceholderText(tr('auto.views_quick_add_dialog.83_optional_beschreibung_5622cc90'))
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
    
    def _category_pairs_structured(self, typ: str) -> list[tuple[str, str]]:
        """Dropdown-Reihenfolge: Favoriten zuerst, danach manuelle Nutzungshäufigkeit."""
        try:
            return self.cats.list_for_tracking_dropdown(typ)
        except Exception as e:
            logger.debug("category dropdown order: %s", e)
            try:
                return self.cats.list_names_tree(typ)
            except Exception:
                return [(n, n) for n in self.cats.list_names(typ)]

    def _update_categories(self):
        """Aktualisiert Kategorien nach Typ – gruppiert (Favoriten/Fix/Wiederkehrend/Übrige),
        baum- und häufigkeitssortiert, mit Suchfeld."""
        typ = self.typ_combo.currentData() or db_typ_from_display(self.typ_combo.currentText())

        current_data = self.cat_combo.currentData() or self.cat_combo.currentText().strip()

        try:
            from views.category_picker import populate_grouped_combo
            grouped = self.cats.list_for_tracking_dropdown_grouped(typ)
            if grouped:
                populate_grouped_combo(self.cat_combo, grouped)
            else:
                raise ValueError("leer")
        except Exception as e:
            logger.debug("gruppierter Picker, Fallback flach: %s", e)
            self.cat_combo.clear()
            for label, real in self._category_pairs_structured(typ):
                self.cat_combo.addItem(label, real)
            try:
                completer = self.cat_combo.completer()
                completer.setCompletionMode(QCompleter.PopupCompletion)
                completer.setFilterMode(Qt.MatchContains)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
            except Exception as e2:
                logger.debug("category completer: %s", e2)

        # Vorherige Auswahl wiederherstellen (über echte itemData)
        if current_data:
            for i in range(self.cat_combo.count()):
                if self.cat_combo.itemData(i) == current_data:
                    self.cat_combo.setCurrentIndex(i)
                    break

    def _validate(self) -> bool:
        """Prüft ob alle Pflichtfelder ausgefüllt sind"""
        if not self.cat_combo.currentText().strip():
            QMessageBox.warning(self, tr('dlg.hinweis'), tr("dlg.bitte_eine_kategorie_auswaehlen"))
            return False
        
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, tr('dlg.hinweis'), tr("dlg.bitte_einen_betrag_0"))
            return False
        
        return True
    
    def _save_entry(self) -> bool:
        """Speichert den Eintrag"""
        if not self._validate():
            return False
        
        d = self.date_edit.date().toPython()
        typ = self.typ_combo.currentData() or db_typ_from_display(self.typ_combo.currentText())
        typ = normalize_typ(typ)
        from views.category_picker import resolve_combo_category
        category = resolve_combo_category(self.cat_combo)
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
