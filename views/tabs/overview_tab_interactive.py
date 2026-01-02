"""
Interaktive, moderne Übersichts-Ansicht für Budgetmanager
Version 0.18.1 - Mit Animationen, Hover-Effekten und interaktiven Diagrammen
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, 
    QRect, QPoint, Property, Signal, QSize
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QGroupBox,
    QFrame, QScrollArea, QPushButton, QGridLayout, QProgressBar,
    QGraphicsOpacityEffect, QSizePolicy, QSpacerItem
)
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QLineSeries, 
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
    QHorizontalBarSeries, QScatterSeries
)
from PySide6.QtGui import (
    QPainter, QFont, QColor, QPen, QBrush, QLinearGradient,
    QCursor, QPalette, QIcon
)

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from settings import Settings

MONTHS = ["Gesamtes Jahr","Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
MONTH_NAMES_SHORT = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]


def format_currency(value: float) -> str:
    """Formatiere Währung mit Tausender-Trenner"""
    s = f"{abs(value):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if value < 0 else ''}{s} €"


class AnimatedKPICard(QFrame):
    """
    Animierte KPI-Karte mit Hover-Effekt und Click-Interaktion
    """
    clicked = Signal(str)  # Emitted mit KPI-Name
    
    def __init__(self, title: str, value: str = "0 €", 
                 icon: str = "💰", color: str = "#2196F3", parent=None):
        super().__init__(parent)
        self.title = title
        self.base_color = QColor(color)
        self.hover_color = QColor(color).lighter(110)
        self.is_hovered = False
        
        # Setup Frame
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(140)
        self.setMaximumHeight(180)
        
        # Opacity Effect für Fade-In
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Icon + Title Row
        top_layout = QHBoxLayout()
        
        self.icon_label = QLabel(icon)
        font = QFont()
        font.setPointSize(32)
        self.icon_label.setFont(font)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        top_layout.addWidget(self.icon_label)
        top_layout.addWidget(self.title_label, 1)
        layout.addLayout(top_layout)
        
        # Value Label (groß und zentriert)
        self.value_label = QLabel(value)
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)
        
        # Change Indicator (klein unten)
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignCenter)
        self.change_label.setStyleSheet("font-size: 9pt; color: #666;")
        layout.addWidget(self.change_label)
        
        # Animationen vorbereiten
        self._setup_animations()
        
    def _setup_animations(self):
        """Setup Fade-In Animation"""
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(800)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
    
    def animate_in(self, delay: int = 0):
        """Fade-In Animation mit Verzögerung"""
        if delay > 0:
            QTimer.singleShot(delay, self.fade_in.start)
        else:
            self.fade_in.start()
    
    def update_value(self, value: str, change_text: str = ""):
        """Update Wert mit optionalem Change-Indikator"""
        self.value_label.setText(value)
        if change_text:
            self.change_label.setText(change_text)
    
    def enterEvent(self, event):
        """Hover-Effekt: Leichtes Highlight"""
        self.is_hovered = True
        self.setStyleSheet(f"""
            AnimatedKPICard {{
                background-color: {self.hover_color.name()};
                border: 2px solid {self.base_color.name()};
                border-radius: 12px;
            }}
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hover-Ende: Zurück zu Normal"""
        self.is_hovered = False
        self.setStyleSheet(f"""
            AnimatedKPICard {{
                border: 2px solid {self.base_color.name()};
                border-radius: 12px;
            }}
        """)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Click-Event: Details anzeigen"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.title)
        super().mousePressEvent(event)


class AnimatedProgressBar(QWidget):
    """
    Animierte Progress-Bar mit Gradient und Prozent-Anzeige
    """
    def __init__(self, label: str, max_value: float = 100, parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.current_value = 0
        self.target_value = 0
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Label Row
        label_row = QHBoxLayout()
        self.label = QLabel(label)
        self.label.setStyleSheet("font-weight: bold;")
        self.percent_label = QLabel("0%")
        self.percent_label.setAlignment(Qt.AlignRight)
        label_row.addWidget(self.label)
        label_row.addWidget(self.percent_label)
        layout.addLayout(label_row)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(25)
        layout.addWidget(self.progress)
        
        # Animation Timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
    
    def set_value(self, value: float, animated: bool = True):
        """Setze Wert mit optionaler Animation"""
        self.target_value = min(value, self.max_value)
        
        if animated:
            self.animation_timer.start(20)  # 50 FPS
        else:
            self.current_value = self.target_value
            self._update_display()
    
    def _animate_step(self):
        """Ein Schritt der Animation"""
        diff = self.target_value - self.current_value
        
        if abs(diff) < 0.5:
            self.current_value = self.target_value
            self.animation_timer.stop()
        else:
            self.current_value += diff * 0.15  # Ease-Out
        
        self._update_display()
    
    def _update_display(self):
        """Aktualisiere Progress Bar und Prozent"""
        percent = int((self.current_value / self.max_value) * 100)
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        
        # Farbe je nach Wert
        if percent < 50:
            color = "#4CAF50"  # Grün
        elif percent < 80:
            color = "#FF9800"  # Orange
        else:
            color = "#f44336"  # Rot
        
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: #f0f0f0;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)


class InteractiveChart(QChartView):
    """
    Interaktives Diagramm mit Hover-Tooltips
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(300)
        
        # Chart Setup
        self._chart = QChart()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        self._chart.setAnimationDuration(1000)
        self.setChart(self._chart)
        
        # Interaktivität
        self.setMouseTracking(True)
    
    def create_pie_chart(self, data: dict, title: str = ""):
        """Erstelle Pie Chart mit Daten"""
        self._chart.removeAllSeries()
        
        series = QPieSeries()
        series.setHoleSize(0.35)  # Donut-Chart
        
        for label, value in data.items():
            slice = series.append(label, value)
            slice.setLabelVisible(True)
            slice.setLabelColor(Qt.white)
            
            # Hover-Effekt
            slice.hovered.connect(lambda state, s=slice: self._on_slice_hover(s, state))
        
        self._chart.addSeries(series)
        self._chart.setTitle(title)
        self._chart.legend().setAlignment(Qt.AlignRight)
    
    def _on_slice_hover(self, slice, state):
        """Hover-Effekt für Pie-Slices"""
        if state:
            slice.setExploded(True)
            slice.setLabelVisible(True)
        else:
            slice.setExploded(False)
    
    def create_line_chart(self, data: dict, title: str = "", y_label: str = ""):
        """Erstelle Line Chart"""
        self._chart.removeAllSeries()
        
        series = QLineSeries()
        
        for x, y in enumerate(data.values()):
            series.append(x, y)
        
        pen = QPen(QColor("#2196F3"))
        pen.setWidth(3)
        series.setPen(pen)
        
        self._chart.addSeries(series)
        self._chart.setTitle(title)
        
        # Achsen
        axis_x = QBarCategoryAxis()
        axis_x.append(list(data.keys()))
        self._chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setTitleText(y_label)
        self._chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)


class OverviewTab(QWidget):
    """
    Moderne, interaktive Übersichts-Ansicht
    """
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.settings = Settings()
        self.budget = BudgetModel(conn)
        self.track = TrackingModel(conn)
        
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
    
    def _setup_ui(self):
        """Setup UI mit modernem Layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        
        # === HEADER MIT FILTERN ===
        header = self._create_header()
        main_layout.addWidget(header)
        
        # === SCROLL AREA für gesamten Content ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)
        
        # === KPI CARDS ===
        self.kpi_section = self._create_kpi_section()
        content_layout.addWidget(self.kpi_section)
        
        # === BUDGET OVERVIEW ===
        budget_section = self._create_budget_section()
        content_layout.addWidget(budget_section)
        
        # === CHARTS ROW ===
        charts_row = self._create_charts_row()
        content_layout.addWidget(charts_row)
        
        # === RECENT TRANSACTIONS ===
        transactions_section = self._create_transactions_section()
        content_layout.addWidget(transactions_section)
        
        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
    
    def _create_header(self) -> QWidget:
        """Erstelle Header mit Filtern und Refresh-Button"""
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header.setStyleSheet("""
            QFrame {
                background-color: palette(window);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Title
        title = QLabel("📊 Finanzübersicht")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Filter
        layout.addWidget(QLabel("Jahr:"))
        self.year_combo = QComboBox()
        self._reload_years()
        layout.addWidget(self.year_combo)
        
        layout.addWidget(QLabel("Monat:"))
        self.month_combo = QComboBox()
        self.month_combo.addItems(MONTHS)
        self.month_combo.setCurrentIndex(date.today().month)
        layout.addWidget(self.month_combo)
        
        # Refresh Button
        self.btn_refresh = QPushButton("🔄 Aktualisieren")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        layout.addWidget(self.btn_refresh)
        
        return header
    
    def _create_kpi_section(self) -> QWidget:
        """Erstelle KPI Cards Section"""
        section = QGroupBox("Kennzahlen auf einen Blick")
        section.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        
        layout = QGridLayout(section)
        layout.setSpacing(15)
        
        # KPI Cards erstellen
        self.kpi_income = AnimatedKPICard("Einnahmen", "0 €", "💰", "#4CAF50")
        self.kpi_expenses = AnimatedKPICard("Ausgaben", "0 €", "💸", "#f44336")
        self.kpi_savings = AnimatedKPICard("Ersparnisse", "0 €", "💎", "#FF9800")
        self.kpi_balance = AnimatedKPICard("Saldo", "0 €", "📈", "#2196F3")
        self.kpi_rate = AnimatedKPICard("Sparquote", "0%", "📊", "#9C27B0")
        
        # Ins Grid layout
        layout.addWidget(self.kpi_income, 0, 0)
        layout.addWidget(self.kpi_expenses, 0, 1)
        layout.addWidget(self.kpi_savings, 0, 2)
        layout.addWidget(self.kpi_balance, 1, 0)
        layout.addWidget(self.kpi_rate, 1, 1)
        
        # Click-Handler
        self.kpi_income.clicked.connect(self._on_kpi_clicked)
        self.kpi_expenses.clicked.connect(self._on_kpi_clicked)
        self.kpi_savings.clicked.connect(self._on_kpi_clicked)
        self.kpi_balance.clicked.connect(self._on_kpi_clicked)
        self.kpi_rate.clicked.connect(self._on_kpi_clicked)
        
        return section
    
    def _create_budget_section(self) -> QWidget:
        """Erstelle Budget Overview mit Progress Bars"""
        section = QGroupBox("Budget-Übersicht")
        section.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        
        layout = QVBoxLayout(section)
        
        # Container für Progress Bars
        self.budget_container = QVBoxLayout()
        layout.addLayout(self.budget_container)
        
        return section
    
    def _create_charts_row(self) -> QWidget:
        """Erstelle Charts Sektion"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setSpacing(15)
        
        # Pie Chart: Ausgaben nach Kategorie
        self.pie_chart = InteractiveChart()
        pie_group = QGroupBox("Ausgaben nach Kategorie")
        pie_layout = QVBoxLayout(pie_group)
        pie_layout.addWidget(self.pie_chart)
        layout.addWidget(pie_group)
        
        # Line Chart: Trend über Zeit
        self.line_chart = InteractiveChart()
        line_group = QGroupBox("Trend: Letzte 12 Monate")
        line_layout = QVBoxLayout(line_group)
        line_layout.addWidget(self.line_chart)
        layout.addWidget(line_group)
        
        return container
    
    def _create_transactions_section(self) -> QWidget:
        """Erstelle Recent Transactions Liste"""
        section = QGroupBox("Letzte Transaktionen")
        section.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        
        layout = QVBoxLayout(section)
        
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(4)
        self.transactions_table.setHorizontalHeaderLabels(["Datum", "Kategorie", "Beschreibung", "Betrag"])
        self.transactions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.transactions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.transactions_table.setAlternatingRowColors(True)
        self.transactions_table.horizontalHeader().setStretchLastSection(True)
        self.transactions_table.setMaximumHeight(250)
        
        layout.addWidget(self.transactions_table)
        
        return section
    
    def _reload_years(self):
        """Lade verfügbare Jahre"""
        self.year_combo.clear()
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT jahr FROM tracking ORDER BY jahr DESC")
        years = [str(row[0]) for row in cursor.fetchall()]
        
        if not years:
            years = [str(date.today().year)]
        
        self.year_combo.addItems(years)
        current_year = str(date.today().year)
        if current_year in years:
            self.year_combo.setCurrentText(current_year)
    
    def _connect_signals(self):
        """Verbinde Signals"""
        self.year_combo.currentTextChanged.connect(self._on_filter_changed)
        self.month_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.btn_refresh.clicked.connect(self.refresh_data)
    
    def _load_initial_data(self):
        """Lade initiale Daten"""
        # Kleine Verzögerung für smooth Start
        QTimer.singleShot(100, self.refresh_data)
    
    def refresh_data(self):
        """Aktualisiere alle Daten mit Animationen"""
        year = int(self.year_combo.currentText())
        month_idx = self.month_combo.currentIndex()
        
        # KPIs berechnen
        if month_idx == 0:  # Gesamtes Jahr
            income, expenses, savings = self._calculate_yearly_kpis(year)
        else:
            income, expenses, savings = self._calculate_monthly_kpis(year, month_idx)
        
        balance = income - expenses
        savings_rate = (savings / income * 100) if income > 0 else 0
        
        # KPIs updaten mit Animation
        self.kpi_income.update_value(format_currency(income))
        self.kpi_income.animate_in(0)
        
        self.kpi_expenses.update_value(format_currency(expenses))
        self.kpi_expenses.animate_in(100)
        
        self.kpi_savings.update_value(format_currency(savings))
        self.kpi_savings.animate_in(200)
        
        self.kpi_balance.update_value(format_currency(balance))
        self.kpi_balance.animate_in(300)
        
        self.kpi_rate.update_value(f"{savings_rate:.1f}%")
        self.kpi_rate.animate_in(400)
        
        # Budget Progress Bars updaten
        self._update_budget_progress(year, month_idx)
        
        # Charts updaten
        self._update_charts(year, month_idx)
        
        # Transaktionen laden
        self._load_recent_transactions(year, month_idx)
    
    def _calculate_monthly_kpis(self, year: int, month: int):
        """Berechne KPIs für einen Monat"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT typ, SUM(betrag) 
            FROM tracking 
            WHERE jahr = ? AND monat = ?
            GROUP BY typ
        """, (year, month))
        
        income = expenses = savings = 0
        for typ, betrag in cursor.fetchall():
            if typ == "Einkommen":
                income += betrag
            elif typ == "Ausgaben":
                expenses += abs(betrag)
            elif typ == "Ersparnisse":
                savings += betrag
        
        return income, expenses, savings
    
    def _calculate_yearly_kpis(self, year: int):
        """Berechne KPIs für gesamtes Jahr"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT typ, SUM(betrag) 
            FROM tracking 
            WHERE jahr = ?
            GROUP BY typ
        """, (year,))
        
        income = expenses = savings = 0
        for typ, betrag in cursor.fetchall():
            if typ == "Einkommen":
                income += betrag
            elif typ == "Ausgaben":
                expenses += abs(betrag)
            elif typ == "Ersparnisse":
                savings += betrag
        
        return income, expenses, savings
    
    def _update_budget_progress(self, year: int, month_idx: int):
        """Update Budget Progress Bars"""
        # Clear existing
        while self.budget_container.count():
            item = self.budget_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if month_idx == 0:
            return  # Kein Budget für Gesamtjahr
        
        # Lade Budget und Ausgaben
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT k.kategorie, b.betrag as budget, 
                   COALESCE(SUM(ABS(t.betrag)), 0) as ausgaben
            FROM kategorien k
            LEFT JOIN budget b ON k.kategorie = b.kategorie 
                AND b.jahr = ? AND b.monat = ?
            LEFT JOIN tracking t ON k.kategorie = t.kategorie 
                AND t.jahr = ? AND t.monat = ? AND t.typ = 'Ausgaben'
            WHERE b.betrag > 0
            GROUP BY k.kategorie, b.betrag
            ORDER BY (COALESCE(SUM(ABS(t.betrag)), 0) / b.betrag) DESC
            LIMIT 8
        """, (year, month_idx, year, month_idx))
        
        for kategorie, budget, ausgaben in cursor.fetchall():
            percent = (ausgaben / budget * 100) if budget > 0 else 0
            
            bar = AnimatedProgressBar(f"{kategorie}: {format_currency(ausgaben)} / {format_currency(budget)}", budget)
            bar.set_value(ausgaben, animated=True)
            self.budget_container.addWidget(bar)
    
    def _update_charts(self, year: int, month_idx: int):
        """Update Charts"""
        # Pie Chart: Top Kategorien
        cursor = self.conn.cursor()
        
        if month_idx == 0:
            cursor.execute("""
                SELECT kategorie, SUM(ABS(betrag)) as total
                FROM tracking
                WHERE jahr = ? AND typ = 'Ausgaben'
                GROUP BY kategorie
                ORDER BY total DESC
                LIMIT 8
            """, (year,))
        else:
            cursor.execute("""
                SELECT kategorie, SUM(ABS(betrag)) as total
                FROM tracking
                WHERE jahr = ? AND monat = ? AND typ = 'Ausgaben'
                GROUP BY kategorie
                ORDER BY total DESC
                LIMIT 8
            """, (year, month_idx))
        
        pie_data = {row[0]: row[1] for row in cursor.fetchall()}
        self.pie_chart.create_pie_chart(pie_data, "")
        
        # Line Chart: 12-Monats-Trend
        cursor.execute("""
            SELECT monat, SUM(ABS(betrag)) as total
            FROM tracking
            WHERE jahr = ? AND typ = 'Ausgaben'
            GROUP BY monat
            ORDER BY monat
        """, (year,))
        
        line_data = {}
        for month, total in cursor.fetchall():
            if month > 0 and month <= 12:
                line_data[MONTH_NAMES_SHORT[month-1]] = total
        
        self.line_chart.create_line_chart(line_data, "", "Ausgaben (€)")
    
    def _load_recent_transactions(self, year: int, month_idx: int):
        """Lade letzte Transaktionen"""
        self.transactions_table.setRowCount(0)
        
        cursor = self.conn.cursor()
        
        if month_idx == 0:
            cursor.execute("""
                SELECT datum, kategorie, beschreibung, betrag
                FROM tracking
                WHERE jahr = ?
                ORDER BY datum DESC
                LIMIT 10
            """, (year,))
        else:
            cursor.execute("""
                SELECT datum, kategorie, beschreibung, betrag
                FROM tracking
                WHERE jahr = ? AND monat = ?
                ORDER BY datum DESC
                LIMIT 10
            """, (year, month_idx))
        
        for row_idx, (datum, kategorie, beschreibung, betrag) in enumerate(cursor.fetchall()):
            self.transactions_table.insertRow(row_idx)
            
            self.transactions_table.setItem(row_idx, 0, QTableWidgetItem(datum))
            self.transactions_table.setItem(row_idx, 1, QTableWidgetItem(kategorie))
            self.transactions_table.setItem(row_idx, 2, QTableWidgetItem(beschreibung))
            
            betrag_item = QTableWidgetItem(format_currency(betrag))
            betrag_item.setForeground(QColor("#4CAF50") if betrag > 0 else QColor("#f44336"))
            self.transactions_table.setItem(row_idx, 3, betrag_item)
    
    def _on_filter_changed(self):
        """Filter wurde geändert"""
        self.refresh_data()
    
    def _on_kpi_clicked(self, kpi_name: str):
        """KPI Card wurde geklickt - zeige Details"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, f"{kpi_name} Details",
            f"Detaillierte Ansicht für {kpi_name} wird in einer zukünftigen Version verfügbar sein.\n\n"
            f"Geplante Features:\n"
            f"• Detaillierte Aufschlüsselung\n"
            f"• Historischer Vergleich\n"
            f"• Export-Funktion\n"
            f"• Trend-Analyse"
        )
