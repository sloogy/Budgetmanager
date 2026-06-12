from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QPushButton, QComboBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from utils.money import format_money
from views.ui_colors import ui_colors

from model.tracking_model import TrackingModel
from model.category_model import CategoryModel
from model.budget_model import BudgetModel
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


class GlobalSearchDialog(QDialog):
    """Globale Suche über alle Daten (Strg+F)"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.tracking = TrackingModel(conn)
        self.cats = CategoryModel(conn)
        self.budget = BudgetModel(conn)
        self.selected_result = None  # Stores selected item on double-click

        self.setWindowTitle(tr("dlg.global_search"))
        self.setMinimumSize(800, 500)
        
        layout = QVBoxLayout()
        
        # === SUCHZEILE ===
        search_row = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search.placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_input, 3)
        
        search_row.addWidget(QLabel(tr("search.search_in")))
        self.search_scope = QComboBox()
        self.search_scope.addItems([tr("search.everywhere"), tr("tab.tracking"), tr("tab.categories"), tr("lbl.budget")])
        self.search_scope.currentIndexChanged.connect(self._do_search)
        search_row.addWidget(self.search_scope, 1)
        
        layout.addLayout(search_row)
        
        # === ERGEBNISSE ===
        self.result_label = QLabel(tr("search.results_label"))
        layout.addWidget(self.result_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([tr("header.type"), tr("header.source"), tr("header.category"), tr("header.details"), tr("lbl.amount")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)
        
        # === BUTTONS ===
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
        # Timer für verzögerte Suche
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_search)
        
        # Fokus auf Suchfeld
        self.search_input.setFocus()
    
    def _on_search_changed(self):
        """Verzögerte Suche bei Texteingabe"""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms Verzögerung
    
    def _do_search(self):
        """Führt die Suche durch"""
        query = self.search_input.text().strip().lower()
        scope = self.search_scope.currentText()
        
        self.table.setRowCount(0)
        
        if len(query) < 2:
            self.result_label.setText("Ergebnisse: (mindestens 2 Zeichen eingeben)")
            return
        
        results = []
        
        # === TRACKING DURCHSUCHEN ===
        if scope in [tr("search.everywhere"), tr("tab.tracking")]:
            rows = self.tracking.list_filtered(search_text=query)
            for r in rows:
                results.append({
                    "type": tr("search.type_tracking"),
                    "source": r.d.strftime("%d.%m.%Y"),
                    "category": r.category,
                    "details": r.details,
                    "value": format_money(r.amount),
                    "color": None
                })
        
        # === KATEGORIEN DURCHSUCHEN ===
        if scope in [tr("search.everywhere"), tr("tab.categories")]:
            for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
                for c in self.cats.list(typ):
                    if query in c.name.lower():
                        flags = []
                        if c.is_fix:
                            flags.append(tr("tracking.title.fixcosts"))
                        if c.is_recurring:
                            flags.append(tr("lbl.recurring"))
                        results.append({
                            "type": tr("search.type_category"),
                            "source": typ,
                            "category": c.name,
                            "details": ", ".join(flags) if flags else "-",
                            "value": "-",
                            "color": QColor(ui_colors(self).accent)
                        })
        
        # === BUDGET DURCHSUCHEN ===
        if scope in [tr("search.everywhere"), tr("tab.budget")]:
            for year in self.budget.years():
                for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
                    matrix = self.budget.get_matrix(year, typ)
                    for cat, months in matrix.items():
                        if query in cat.lower():
                            total = sum(float(v) for v in months.values())
                            if total > 0:
                                results.append({
                                    "type": tr("search.type_budget"),
                                    "source": f"{year} / {typ}",
                                    "category": cat,
                                    "details": tr("lbl.entire_year"),
                                    "value": format_money(total),
                                    "color": QColor(ui_colors(self).warning)
                                })
        
        # Ergebnisse anzeigen
        self.result_label.setText(f"Ergebnisse: {len(results)} gefunden")
        
        for r in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            for col, key in enumerate(["type", "source", "category", "details", "value"]):
                item = QTableWidgetItem(r[key])
                if r["color"]:
                    item.setForeground(r["color"])
                if col == 4:  # Wert rechtsbündig
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, item)
        
        self.table.resizeColumnsToContents()
    
    def _on_double_click(self):
        """Bei Doppelklick: Dialog akzeptieren und Ergebnis speichern."""
        row = self.table.currentRow()
        if row < 0:
            return
        type_item = self.table.item(row, 0)
        if not type_item:
            return
        type_text = type_item.text()

        # Determine which tab to navigate to
        if tr("search.type_budget") in type_text:
            tab_key = "budget"
        elif tr("search.type_tracking") in type_text:
            tab_key = "tracking"
        elif tr("search.type_category") in type_text:
            tab_key = "categories"
        else:
            tab_key = None

        self.selected_result = {
            "tab": tab_key,
            "type": type_text,
            "source": self.table.item(row, 1).text() if self.table.item(row, 1) else "",
            "category": self.table.item(row, 2).text() if self.table.item(row, 2) else "",
            "details": self.table.item(row, 3).text() if self.table.item(row, 3) else "",
            "value": self.table.item(row, 4).text() if self.table.item(row, 4) else "",
        }
        self.accept()
