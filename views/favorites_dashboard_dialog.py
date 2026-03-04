from __future__ import annotations

"""
Favoriten-Dashboard für Budgetmanager
Zeigt eine Schnellübersicht aller favoritisierten Kategorien mit Budget/Gebucht-Vergleich
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QDialogButtonBox,
    QProgressBar, QWidget, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import sqlite3
from datetime import date

from model.favorites_model import FavoritesModel
from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from utils.money import format_money
from views.ui_colors import ui_colors


import logging
from utils.i18n import tr, trf, display_typ
from model.typ_constants import normalize_typ, TYP_INCOME
logger = logging.getLogger(__name__)

class FavoritesDashboardDialog(QDialog):
    """Dashboard für Favoriten-Kategorien"""
    
    def __init__(self, conn: sqlite3.Connection, current_year: int = None, 
                 current_month: int = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.favorites_model = FavoritesModel(conn)
        self._budget_model = BudgetModel(conn)
        self._tracking_model = TrackingModel(conn)
        
        # Aktuelles Jahr/Monat
        if current_year is None or current_month is None:
            today = date.today()
            self.current_year = today.year
            self.current_month = today.month
        else:
            self.current_year = current_year
            self.current_month = current_month
        
        self.setWindowTitle(trf("dlg.favorites_dashboard_title", month=self._month_name(self.current_month), year=self.current_year))
        self.setMinimumSize(800, 500)
        
        self._setup_ui()
        self._load_favorites()
        
    def _setup_ui(self):
        """Erstellt das UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(
            trf(
                "favorites.header_html",
                month=self._month_name(self.current_month),
                year=self.current_year,
            )
        )
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)
        
        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            tr("header.type"),
            tr("header.category"), 
            tr("header.budget"), 
            tr("lbl.gebucht"),
            tr("lbl.rest"),
            tr("lbl.savings_goal_progress")
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 180)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        # Zusammenfassung
        self.summary_label = QLabel()
        self.summary_label.setTextFormat(Qt.RichText)
        self.summary_label.setStyleSheet("padding: 8px; font-size: 13px;")
        layout.addWidget(self.summary_label)
        
        # Button-Leiste
        btn_layout = QHBoxLayout()
        
        btn_refresh = QPushButton(tr("overview.btn.refresh"))
        btn_refresh.clicked.connect(self._load_favorites)
        btn_layout.addWidget(btn_refresh)
        
        btn_manage = QPushButton(tr("favorites.btn_manage"))
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
            item = QTableWidgetItem(tr("favorites.empty") + " " +
                                     tr("dlg.fuegen_sie_favoriten_im"))
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
            typ_key = normalize_typ(typ)
            rest = (booked_amount - budget_amount) if typ_key == TYP_INCOME else (budget_amount - booked_amount)
            
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
            typ_item = QTableWidgetItem(display_typ(typ))
            typ_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, typ_item)
            
            # Kategorie-Name
            name_item = QTableWidgetItem(f"⭐ {category}")
            self.table.setItem(row, 1, name_item)
            
            # Budget
            budget_item = QTableWidgetItem(format_money(budget_amount))
            budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, budget_item)
            
            # Gebucht
            booked_item = QTableWidgetItem(format_money(booked_amount))
            booked_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            c = ui_colors(self)
            # Farbcodierung
            if budget_amount > 0 and booked_amount > budget_amount:
                booked_item.setForeground(QColor(c.negative))
            elif budget_amount > 0 and booked_amount > budget_amount * 0.9:
                booked_item.setForeground(QColor(c.warning))
            else:
                booked_item.setForeground(QColor(c.ok))
            self.table.setItem(row, 3, booked_item)
            
            # Rest
            rest_item = QTableWidgetItem(format_money(rest))
            rest_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if rest < 0:
                rest_item.setForeground(QColor(c.negative))
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
            color = c.progress_color(progress)
                
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid {c.border};
                    border-radius: 4px;
                    text-align: center;
                    background: {c.bg_panel};
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
        summary_text = trf("lbl.summary_total_budget",
            budget=format_money(total_budget), booked=format_money(total_booked))
        if total_rest >= 0:
            summary_text += trf("lbl.summary_remaining", color=c.ok, amount=format_money(total_rest))
        else:
            summary_text += trf("lbl.summary_overrun", color=c.negative, amount=format_money(abs(total_rest)))
            
        self.summary_label.setText(summary_text)
        
    def _get_budget_amount(self, typ: str, category: str) -> float:
        """Holt den Budget-Betrag für eine Kategorie (typ + category Name)"""
        return self._budget_model.get_amount(
            self.current_year, self.current_month, typ, category
        )
        
    def _get_booked_amount(self, typ: str, category: str) -> float:
        """Holt den gebuchten Betrag für eine Kategorie aus der tracking-Tabelle"""
        return self._tracking_model.get_month_total(
            self.current_year, self.current_month, typ, category
        )
        
    def _manage_favorites(self):
        """Öffnet die Favoriten-Verwaltung"""
        QMessageBox.information(
            self,
            tr("favorites.manage.title"),
            tr("favorites.manage.body")
        )
        
    def _month_name(self, month: int) -> str:
        """Gibt den Monatsnamen zurück"""
        return tr(f"month.{month}") if 1 <= month <= 12 else str(month)
