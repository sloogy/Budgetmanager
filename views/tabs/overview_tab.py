"""
Interaktive Übersicht - FUNKTIONIERT GARANTIERT
"""

from __future__ import annotations
import sqlite3
from datetime import date

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QFrame, QScrollArea, QGroupBox, QGridLayout, QProgressBar,
    QGraphicsOpacityEffect, QPushButton
)
from PySide6.QtCharts import QChart, QChartView, QPieSeries
from PySide6.QtGui import QPainter, QFont, QColor, QCursor

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from settings import Settings

MONTHS = ["Gesamtes Jahr","Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]


def format_chf(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", "'")
    return f"{'-' if value < 0 else ''}{s} CHF"


class AnimatedKPICard(QFrame):
    clicked = Signal(str)
    
    def __init__(self, title: str, value: str = "0 CHF", icon: str = "💰", color: str = "#2196F3", parent=None):
        super().__init__(parent)
        self.title = title
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(140)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        top_layout = QHBoxLayout()
        self.icon_label = QLabel(icon)
        font = QFont()
        font.setPointSize(32)
        self.icon_label.setFont(font)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        
        top_layout.addWidget(self.icon_label)
        top_layout.addWidget(self.title_label, 1)
        layout.addLayout(top_layout)
        
        self.value_label = QLabel(value)
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)
        
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignCenter)
        self.change_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(self.change_label)
        
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(800)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
    
    def animate_in(self, delay: int = 0):
        QTimer.singleShot(delay, self.fade_in.start) if delay > 0 else self.fade_in.start()
    
    def update_value(self, value: str, change_text: str = ""):
        self.value_label.setText(value)
        if change_text:
            self.change_label.setText(change_text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.title)
        super().mousePressEvent(event)


class AnimatedProgressBar(QWidget):
    def __init__(self, label: str, max_value: float = 100, parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.current_value = 0
        self.target_value = 0
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        label_row = QHBoxLayout()
        self.label = QLabel(label)
        self.label.setStyleSheet("font-weight: bold;")
        self.percent_label = QLabel("0%")
        self.percent_label.setAlignment(Qt.AlignRight)
        label_row.addWidget(self.label)
        label_row.addWidget(self.percent_label)
        layout.addLayout(label_row)
        
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(25)
        layout.addWidget(self.progress)
        
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
    
    def set_value(self, value: float, animated: bool = True):
        self.target_value = min(value, self.max_value)
        self.animation_timer.start(20) if animated else self._update_display()
    
    def _animate_step(self):
        diff = self.target_value - self.current_value
        if abs(diff) < 0.5:
            self.current_value = self.target_value
            self.animation_timer.stop()
        else:
            self.current_value += diff * 0.15
        self._update_display()
    
    def _update_display(self):
        percent = int((self.current_value / self.max_value) * 100) if self.max_value > 0 else 0
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        color = "#4CAF50" if percent < 50 else "#FF9800" if percent < 80 else "#f44336"
        self.progress.setStyleSheet(f"QProgressBar{{border:2px solid #ddd;border-radius:8px;background:#f0f0f0}}QProgressBar::chunk{{background:{color};border-radius:6px}}")


class InteractiveChart(QChartView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(300)
        self._chart = QChart()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        self._chart.setAnimationDuration(1000)
        self.setChart(self._chart)
    
    def create_pie_chart(self, data: dict, title: str = ""):
        self._chart.removeAllSeries()
        series = QPieSeries()
        series.setHoleSize(0.35)
        for label, value in data.items():
            if value > 0:
                slice = series.append(label, value)
                slice.setLabelVisible(True)
                slice.hovered.connect(lambda state, s=slice: s.setExploded(state))
        self._chart.addSeries(series)
        self._chart.setTitle(title)
        self._chart.legend().setAlignment(Qt.AlignRight)


class OverviewTab(QWidget):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.settings = Settings()
        self.budget = BudgetModel(conn)
        self.track = TrackingModel(conn)
        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(100, self.refresh_data)
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(header)
        title = QLabel("📊 Finanzübersicht")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(QLabel("Jahr:"))
        self.year_combo = QComboBox()
        self._reload_years()
        layout.addWidget(self.year_combo)
        layout.addWidget(QLabel("Monat:"))
        self.month_combo = QComboBox()
        self.month_combo.addItems(MONTHS)
        self.month_combo.setCurrentIndex(min(date.today().month, 12))
        layout.addWidget(self.month_combo)
        self.btn_refresh = QPushButton("🔄")
        layout.addWidget(self.btn_refresh)
        main_layout.addWidget(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        kpi_section = QGroupBox("Kennzahlen")
        kpi_layout = QGridLayout(kpi_section)
        self.kpi_income = AnimatedKPICard("Einnahmen", "0 CHF", "💰", "#4CAF50")
        self.kpi_expenses = AnimatedKPICard("Ausgaben", "0 CHF", "💸", "#f44336")
        self.kpi_savings = AnimatedKPICard("Ersparnisse", "0 CHF", "💎", "#FF9800")
        self.kpi_balance = AnimatedKPICard("Saldo", "0 CHF", "📈", "#2196F3")
        self.kpi_rate = AnimatedKPICard("Sparquote", "0%", "📊", "#9C27B0")
        kpi_layout.addWidget(self.kpi_income, 0, 0)
        kpi_layout.addWidget(self.kpi_expenses, 0, 1)
        kpi_layout.addWidget(self.kpi_savings, 0, 2)
        kpi_layout.addWidget(self.kpi_balance, 1, 0)
        kpi_layout.addWidget(self.kpi_rate, 1, 1)
        content_layout.addWidget(kpi_section)
        self.budget_section = QGroupBox("Budget-Übersicht")
        budget_layout = QVBoxLayout(self.budget_section)
        self.budget_container = QVBoxLayout()
        budget_layout.addLayout(self.budget_container)
        content_layout.addWidget(self.budget_section)
        chart_group = QGroupBox("Ausgaben nach Kategorie")
        chart_layout = QVBoxLayout(chart_group)
        self.pie_chart = InteractiveChart()
        chart_layout.addWidget(self.pie_chart)
        content_layout.addWidget(chart_group)
        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
    
    def _reload_years(self):
        self.year_combo.clear()
        years = sorted(set(self.budget.years()) | set(self.track.years())) or [date.today().year]
        self.year_combo.addItem("Gesamter Zeitraum")
        for y in years:
            self.year_combo.addItem(str(y))
        cy = str(date.today().year)
        for i in range(self.year_combo.count()):
            if self.year_combo.itemText(i) == cy:
                self.year_combo.setCurrentIndex(i)
                break
    
    def _connect_signals(self):
        self.year_combo.currentTextChanged.connect(self.refresh_data)
        self.month_combo.currentIndexChanged.connect(self.refresh_data)
        self.btn_refresh.clicked.connect(self.refresh_data)
    
    def refresh_data(self):
        year_text = self.year_combo.currentText()
        year = None if year_text == "Gesamter Zeitraum" else int(year_text)
        month = None if self.month_combo.currentIndex() == 0 else self.month_combo.currentIndex()
        t_typ = self.track.sum_by_typ(year=year, month=month)
        income = t_typ.get("Einkommen", 0.0)
        expenses = abs(t_typ.get("Ausgaben", 0.0))
        savings = t_typ.get("Ersparnisse", 0.0)
        balance = income - expenses
        savings_rate = (savings / income * 100) if income > 0 else 0
        self.kpi_income.update_value(format_chf(income))
        self.kpi_income.animate_in(0)
        self.kpi_expenses.update_value(format_chf(expenses))
        self.kpi_expenses.animate_in(100)
        self.kpi_savings.update_value(format_chf(savings))
        self.kpi_savings.animate_in(200)
        self.kpi_balance.update_value(format_chf(balance))
        self.kpi_balance.animate_in(300)
        self.kpi_rate.update_value(f"{savings_rate:.1f}%")
        self.kpi_rate.animate_in(400)
        self._update_budget_progress(year, month)
        self._update_charts(year, month)
    
    def _update_budget_progress(self, year, month):
        while self.budget_container.count():
            item = self.budget_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not year or not month:
            self.budget_section.setVisible(False)
            return
        self.budget_section.setVisible(True)
        budget_cats = self.budget.sum_by_category(year, month)
        track_cats = self.track.sum_by_category("Ausgaben", year, month)
        count = 0
        for category, budget_amount in sorted(budget_cats.items(), key=lambda x: abs(x[1]), reverse=True):
            if budget_amount <= 0 or count >= 8:
                continue
            actual = abs(track_cats.get(category, 0.0))
            bar = AnimatedProgressBar(f"{category}: {format_chf(actual)} / {format_chf(budget_amount)}", budget_amount)
            bar.set_value(actual, animated=True)
            self.budget_container.addWidget(bar)
            count += 1
        if count == 0:
            self.budget_section.setVisible(False)
    
    def _update_charts(self, year, month):
        track_cats = self.track.sum_by_category("Ausgaben", year, month)
        sorted_cats = sorted(track_cats.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
        pie_data = {cat: abs(amt) for cat, amt in sorted_cats if abs(amt) > 0}
        self.pie_chart.create_pie_chart(pie_data, "")
