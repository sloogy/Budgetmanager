"""
Favoriten-Dashboard für Budgetmanager
Zeigt eine Schnellübersicht aller favoritisierten Kategorien mit Budget/Gebucht-Vergleich
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QDialogButtonBox,
    QProgressBar, QWidget, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import sqlite3
from datetime import date

from model.favorites_model import FavoritesModel


class FavoritesDashboardDialog(QDialog):
    """Dashboard für Favoriten-Kategorien"""
    
    def __init__(self, conn: sqlite3.Connection, current_year: int = None, 
                 current_month: int = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.favorites_model = FavoritesModel(conn)
        
        # Aktuelles Jahr/Monat
        if current_year is None or current_month is None:
            today = date.today()
            self.current_year = today.year
            self.current_month = today.month
        else:
            self.current_year = current_year
            self.current_month = current_month
        
        self.setWindowTitle(f"⭐ Favoriten-Dashboard - {self._month_name(self.current_month)} {self.current_year}")
        self.setMinimumSize(800, 500)
        
        self._setup_ui()
        self._load_favorites()
        
    def _setup_ui(self):
        """Erstellt das UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(
            f"<h2>⭐ Favoriten-Übersicht</h2>"
            f"<p>Zeigt Budget vs. Ausgaben für Ihre favorisierten Kategorien "
            f"({self._month_name(self.current_month)} {self.current_year})</p>"
        )
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)
        
        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Typ",
            "Kategorie", 
            "Budget", 
            "Gebucht",
            "Rest",
            "Fortschritt"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 180)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Zusammenfassung
        self.summary_label = QLabel()
        self.summary_label.setTextFormat(Qt.RichText)
        self.summary_label.setStyleSheet("padding: 8px; font-size: 13px;")
        layout.addWidget(self.summary_label)
        
        # Button-Leiste
        btn_layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 Aktualisieren")
        btn_refresh.clicked.connect(self._load_favorites)
        btn_layout.addWidget(btn_refresh)
        
        btn_manage = QPushButton("⚙️ Favoriten verwalten...")
        btn_manage.clicked.connect(self._manage_favorites)
        btn_layout.addWidget(btn_manage)
        
        btn_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        btn_layout.addWidget(buttons)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def _load_favorites(self):
        """Lädt Favoriten-Daten"""
        self.table.setRowCount(0)
        
        # Favoriten holen – gibt Liste von (typ, category) zurück
        favorites = self.favorites_model.list_all()
        
        if not favorites:
            self.table.insertRow(0)
            item = QTableWidgetItem("Keine Favoriten vorhanden. "
                                     "Fügen Sie Favoriten im Budget-Tab über das Kontextmenü hinzu.")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, 6)
            self.summary_label.setText("")
            return
            
        # Für jede Favoriten-Kategorie Daten laden
        total_budget = 0.0
        total_booked = 0.0
        
        for typ, category in favorites:
            # Budget-Daten holen
            budget_amount = self._get_budget_amount(typ, category)
            booked_amount = self._get_booked_amount(typ, category)
            rest = budget_amount - booked_amount
            
            total_budget += budget_amount
            total_booked += booked_amount
            
            # Fortschritt berechnen
            progress = 0
            if budget_amount > 0:
                progress = min(100, int((booked_amount / budget_amount) * 100))
            
            # Zeile hinzufügen
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Typ
            typ_item = QTableWidgetItem(typ)
            typ_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, typ_item)
            
            # Kategorie-Name
            name_item = QTableWidgetItem(f"⭐ {category}")
            self.table.setItem(row, 1, name_item)
            
            # Budget
            budget_item = QTableWidgetItem(f"{budget_amount:,.2f} €")
            budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, budget_item)
            
            # Gebucht
            booked_item = QTableWidgetItem(f"{booked_amount:,.2f} €")
            booked_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Farbcodierung
            if budget_amount > 0 and booked_amount > budget_amount:
                booked_item.setForeground(QColor("#e74c3c"))  # Rot
            elif budget_amount > 0 and booked_amount > budget_amount * 0.9:
                booked_item.setForeground(QColor("#f39c12"))  # Orange
            else:
                booked_item.setForeground(QColor("#27ae60"))  # Grün
            self.table.setItem(row, 3, booked_item)
            
            # Rest
            rest_item = QTableWidgetItem(f"{rest:,.2f} €")
            rest_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if rest < 0:
                rest_item.setForeground(QColor("#e74c3c"))
            self.table.setItem(row, 4, rest_item)
            
            # Fortschrittsbalken
            progress_widget = QWidget()
            progress_layout = QHBoxLayout(progress_widget)
            progress_layout.setContentsMargins(4, 4, 4, 4)
            
            progress_bar = QProgressBar()
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            progress_bar.setValue(progress)
            progress_bar.setFormat(f"{progress}%")
            progress_bar.setFixedHeight(20)
            
            # Farbe je nach Auslastung
            if progress >= 100:
                color = "#e74c3c"  # Rot
            elif progress >= 90:
                color = "#f39c12"  # Orange
            elif progress >= 70:
                color = "#f1c40f"  # Gelb
            else:
                color = "#27ae60"  # Grün
                
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    text-align: center;
                    background: #f0f0f0;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 3px;
                }}
            """)
            
            progress_layout.addWidget(progress_bar)
            self.table.setCellWidget(row, 5, progress_widget)
            
        # Zusammenfassung
        total_rest = total_budget - total_booked
        summary_text = (
            f"Gesamt: <b>{total_budget:,.2f} €</b> Budget | "
            f"<b>{total_booked:,.2f} €</b> Gebucht | "
        )
        
        if total_rest >= 0:
            summary_text += f"<b style='color: #27ae60;'>{total_rest:,.2f} €</b> übrig"
        else:
            summary_text += f"<b style='color: #e74c3c;'>{abs(total_rest):,.2f} €</b> Überschreitung"
            
        self.summary_label.setText(summary_text)
        
    def _get_budget_amount(self, typ: str, category: str) -> float:
        """Holt den Budget-Betrag für eine Kategorie (typ + category Name)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT amount 
                FROM budget 
                WHERE typ = ? AND category = ? AND year = ? AND month = ?
            """, (typ, category, self.current_year, self.current_month))
            result = cursor.fetchone()
            return float(result[0]) if result and result[0] else 0.0
        except Exception:
            return 0.0
        
    def _get_booked_amount(self, typ: str, category: str) -> float:
        """Holt den gebuchten Betrag für eine Kategorie aus der tracking-Tabelle"""
        try:
            ym = f"{self.current_year:04d}-{self.current_month:02d}"
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM tracking
                WHERE typ = ? AND category = ?
                  AND substr(date, 1, 7) = ?
            """, (typ, category, ym))
            result = cursor.fetchone()
            return float(result[0]) if result else 0.0
        except Exception:
            return 0.0
        
    def _manage_favorites(self):
        """Öffnet die Favoriten-Verwaltung"""
        QMessageBox.information(
            self,
            "Favoriten verwalten",
            "Favoriten können im Budget-Tab über das Kontextmenü verwaltet werden:\n\n"
            "• Rechtsklick auf Kategorie → 'Als Favorit markieren'\n"
            "• Rechtsklick auf Favorit → 'Favorit entfernen'\n\n"
            "Favoriten werden oben im Dashboard angezeigt."
        )
        
    def _month_name(self, month: int) -> str:
        """Gibt den Monatsnamen zurück"""
        months = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ]
        return months[month] if 1 <= month <= 12 else str(month)
