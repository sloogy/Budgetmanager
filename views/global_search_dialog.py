from __future__ import annotations
import sqlite3
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QPushButton, QComboBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from model.tracking_model import TrackingModel
from model.category_model import CategoryModel
from model.budget_model import BudgetModel


class GlobalSearchDialog(QDialog):
    """Globale Suche über alle Daten (Strg+F)"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.tracking = TrackingModel(conn)
        self.cats = CategoryModel(conn)
        self.budget = BudgetModel(conn)
        
        self.setWindowTitle("🔍 Globale Suche")
        self.setMinimumSize(800, 500)
        
        layout = QVBoxLayout()
        
        # === SUCHZEILE ===
        search_row = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suchbegriff eingeben...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_input, 3)
        
        search_row.addWidget(QLabel("Suchen in:"))
        self.search_scope = QComboBox()
        self.search_scope.addItems(["Überall", "Tracking", "Kategorien", "Budget"])
        self.search_scope.currentIndexChanged.connect(self._do_search)
        search_row.addWidget(self.search_scope, 1)
        
        layout.addLayout(search_row)
        
        # === ERGEBNISSE ===
        self.result_label = QLabel("Ergebnisse:")
        layout.addWidget(self.result_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Typ", "Quelle", "Kategorie", "Details", "Wert"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
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
        if scope in ["Überall", "Tracking"]:
            rows = self.tracking.list_filtered(search_text=query)
            for r in rows:
                results.append({
                    "type": "📊 Tracking",
                    "source": r.d.strftime("%d.%m.%Y"),
                    "category": r.category,
                    "details": r.details,
                    "value": f"CHF {r.amount:,.2f}".replace(",", "'"),
                    "color": None
                })
        
        # === KATEGORIEN DURCHSUCHEN ===
        if scope in ["Überall", "Kategorien"]:
            for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
                for c in self.cats.list(typ):
                    if query in c.name.lower():
                        flags = []
                        if c.is_fix:
                            flags.append("Fixkosten")
                        if c.is_recurring:
                            flags.append("Wiederkehrend")
                        results.append({
                            "type": "📁 Kategorie",
                            "source": typ,
                            "category": c.name,
                            "details": ", ".join(flags) if flags else "-",
                            "value": "-",
                            "color": QColor(100, 150, 255)
                        })
        
        # === BUDGET DURCHSUCHEN ===
        if scope in ["Überall", "Budget"]:
            for year in self.budget.years():
                for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
                    matrix = self.budget.get_matrix(year, typ)
                    for cat, months in matrix.items():
                        if query in cat.lower():
                            total = sum(float(v) for v in months.values())
                            if total > 0:
                                results.append({
                                    "type": "💰 Budget",
                                    "source": f"{year} / {typ}",
                                    "category": cat,
                                    "details": f"Jahrestotal",
                                    "value": f"CHF {total:,.2f}".replace(",", "'"),
                                    "color": QColor(255, 180, 100)
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
        """Bei Doppelklick könnte man zum entsprechenden Eintrag navigieren"""
        # TODO: Navigation implementieren
        pass
