"""
Kompakte & übersichtliche Finanzübersicht mit klarer Strukturierung
Version 2.1.0 - Vollständig überarbeitet
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
import calendar

from PySide6.QtCore import Qt, QTimer, Signal, QDate, QSignalBlocker, QMargins
from PySide6.QtGui import QPainter, QFont, QCursor, QDoubleValidator, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QFrame, QScrollArea, QGroupBox, QGridLayout, QProgressBar,
    QPushButton, QLineEdit, QCheckBox, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QSpinBox, 
    QAbstractItemView, QSplitter, QTabWidget
)
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel, TrackingRow
from model.category_model import CategoryModel
from model.tags_model import TagsModel
from settings import Settings

MONTHS = ["Gesamtes Jahr", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
RANGES = ["Jahr/Monat", "Letzte 7 Tage", "Letzte 30 Tage", "Letzte 90 Tage", "Benutzerdefiniert"]

TYPES = ["Alle", "Ausgaben", "Einkommen", "Ersparnisse"]
_TYP_ALIASES = {
    "einnahmen": "Einkommen",
    "einkommen": "Einkommen",
    "income": "Einkommen",
    "ausgaben": "Ausgaben",
    "expenses": "Ausgaben",
    "expense": "Ausgaben",
    "ersparnisse": "Ersparnisse",
    "sparen": "Ersparnisse",
    "savings": "Ersparnisse",
}


def _norm_typ(s: str) -> str:
    return _TYP_ALIASES.get(str(s or "").strip().lower(), str(s or "").strip())


def format_chf(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", "'")
    return f"{'-' if value < 0 else ''}{s} CHF"


def _to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _month_range(y: int, m: int) -> tuple[date, date]:
    last = calendar.monthrange(y, m)[1]
    return (date(y, m, 1), date(y, m, last))


class CompactKPICard(QFrame):
    """Kompakte KPI-Karte mit klarem Design"""
    clicked = Signal(str)

    def __init__(self, title: str, value: str = "0 CHF", icon: str = "💰", color: str = "#2196F3", parent=None):
        super().__init__(parent)
        self.title = title
        self._color = color

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(90)
        self.setMinimumWidth(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Icon + Titel in einer Zeile
        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16pt;")
        header.addWidget(icon_label)
        
        title_label = QLabel(title)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        title_label.setFont(font)
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        # Wert prominent
        self.value_label = QLabel(value)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)

        layout.addStretch()

    def update_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self._color = color
            self.value_label.setStyleSheet(f"color: {color};")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.title)
        super().mousePressEvent(event)


class CompactProgressBar(QWidget):
    """Kompakter Fortschrittsbalken mit Beschriftung"""
    def __init__(self, label: str, max_value: float = 100, parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.current_value = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.label = QLabel(label)
        self.label.setFixedWidth(80)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(20)
        layout.addWidget(self.progress)

    def set_values(self, current: float, maximum: float):
        """Setzt aktuellen und maximalen Wert"""
        self.current_value = float(current)
        self.max_value = float(maximum) if maximum > 0 else 1.0
        
        percent = min(int((abs(self.current_value) / self.max_value) * 100), 200)
        self.progress.setValue(min(percent, 100))
        
        # Format: "45% (450 / 1'000 CHF)"
        self.progress.setFormat(
            f"{percent}% ({format_chf(self.current_value)} / {format_chf(self.max_value)})"
        )
        
        # Farbe basierend auf Prozent
        if percent > 100:
            color = "#e74c3c"  # Rot - überschritten
        elif percent > 80:
            color = "#f39c12"  # Orange - fast erreicht
        else:
            color = "#27ae60"  # Grün - OK
            
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
                background: #f0f0f0;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)


class CompactChart(QChartView):
    """Kompaktes Diagramm"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(180)
        self.setMaximumHeight(300)
        self._chart = QChart()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        self._chart.setAnimationDuration(400)
        self._chart.setMargins(QMargins(0, 0, 0, 0))
        self.setChart(self._chart)

    def create_pie_chart(self, data: dict[str, float], title: str = ""):
        self._chart.removeAllSeries()
        
        if not data:
            self._chart.setTitle(title + " (keine Daten)")
            return
            
        series = QPieSeries()
        series.setHoleSize(0.4)

        # Sortiere nach Wert (größte zuerst)
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        
        # Farben
        colors = ["#3498db", "#e74c3c", "#27ae60", "#f39c12", "#9b59b6", 
                  "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b"]
        
        for i, (label, value) in enumerate(sorted_data):
            v = float(value)
            if v <= 0:
                continue
            s = series.append(f"{label}: {format_chf(v)}", v)
            s.setLabelVisible(True)
            s.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
            if i < len(colors):
                s.setColor(colors[i])

        self._chart.addSeries(series)
        self._chart.setTitle(title)
        self._chart.legend().setVisible(False)


class OverviewTab(QWidget):
    """Finanzübersicht Tab"""
    
    # Signal für Schnelleingabe (wird von MainWindow abgehört)
    quick_add_requested = Signal()
    
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.settings = Settings()
        self.budget = BudgetModel(conn)
        self.track = TrackingModel(conn)
        self.categories = CategoryModel(conn)
        self.tags = TagsModel(conn)

        self._tag_name_to_id: dict[str, int] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh_data)

        # Größenbeschränkung
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(100, self.refresh_data)

    # ========== Subtab-Visibility API für main_window ==========
    def get_subtab_specs(self) -> list[tuple[str, str]]:
        """Gibt verfügbare Subtabs zurück für Menü-Einträge.
        Returns: Liste von (key, title) Tupeln
        """
        return [
            ("kpi", "📊 KPI-Karten"),
            ("budget", "📈 Budget-Status"),
            ("charts", "📉 Diagramme"),
            ("filters", "🔍 Filter"),
            ("transactions", "📋 Transaktionen"),
        ]
    
    def apply_subtab_visibility(self, visibility: dict[str, bool]) -> None:
        """Wendet Sichtbarkeits-Einstellungen auf Subtabs an."""
        # KPI Cards
        if hasattr(self, 'kpi_widget'):
            self.kpi_widget.setVisible(visibility.get("kpi", True))
        
        # Budget Status
        if hasattr(self, 'budget_group'):
            self.budget_group.setVisible(visibility.get("budget", True))
        
        # Charts
        if hasattr(self, 'chart_tabs'):
            self.chart_tabs.setVisible(visibility.get("charts", True))
        
        # Filter Tab (im rechten Panel)
        if hasattr(self, 'right_tabs'):
            # Filter ist Tab 0, Transaktionen ist Tab 1
            filter_visible = visibility.get("filters", True)
            trans_visible = visibility.get("transactions", True)
            
            # Tabs können nicht einzeln versteckt werden, 
            # aber wir können sie deaktivieren
            self.right_tabs.setTabVisible(0, filter_visible)
            self.right_tabs.setTabVisible(1, trans_visible)
    
    def set_subtab_visible(self, key: str, visible: bool) -> None:
        """Setzt Sichtbarkeit eines einzelnen Subtabs."""
        vis = {key: visible}
        self.apply_subtab_visibility(vis)

    # ========== UI Setup ==========
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # ScrollArea für Hauptinhalt
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = self._create_left_panel()
        splitter.addWidget(left_widget)
        
        right_widget = self._create_right_panel()
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        
        content_layout.addWidget(splitter)
        scroll.setWidget(content_widget)
        
        main_layout.addWidget(scroll)

    def _create_header(self) -> QWidget:
        """Header mit Zeitraum-Auswahl"""
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header.setMaximumHeight(55)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)

        # Titel
        title = QLabel("📊 Finanzübersicht")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addStretch()
        
        # Schnelleingabe-Button
        self.btn_quick_add = QPushButton("⚡ Schnelleingabe")
        self.btn_quick_add.setToolTip("Schnell einen neuen Tracking-Eintrag erfassen (Ctrl+N)")
        self.btn_quick_add.clicked.connect(self.quick_add_requested.emit)
        layout.addWidget(self.btn_quick_add)

        # Zeitraum
        layout.addWidget(QLabel("Zeitraum:"))
        self.range_combo = QComboBox()
        self.range_combo.addItems(RANGES)
        self.range_combo.setFixedWidth(140)
        layout.addWidget(self.range_combo)

        # Jahr
        layout.addWidget(QLabel("Jahr:"))
        self.year_combo = QComboBox()
        self._reload_years()
        self.year_combo.setFixedWidth(70)
        layout.addWidget(self.year_combo)

        # Monat
        layout.addWidget(QLabel("Monat:"))
        self.month_combo = QComboBox()
        self.month_combo.addItems(MONTHS)
        self.month_combo.setCurrentIndex(min(date.today().month, 12))
        self.month_combo.setFixedWidth(120)
        layout.addWidget(self.month_combo)

        # Refresh
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedWidth(35)
        self.btn_refresh.setToolTip("Daten aktualisieren (F5)")
        layout.addWidget(self.btn_refresh)

        return header

    def _create_left_panel(self) -> QWidget:
        """Linkes Panel: KPIs, Budget, Charts"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(4, 4, 4, 4)

        # KPI Cards
        self.kpi_widget = QWidget()
        kpi_layout = QHBoxLayout(self.kpi_widget)
        kpi_layout.setSpacing(8)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        
        self.card_income = CompactKPICard("Einkommen", "0 CHF", "💰", "#27ae60")
        self.card_expenses = CompactKPICard("Ausgaben", "0 CHF", "💸", "#e74c3c")
        self.card_balance = CompactKPICard("Bilanz", "0 CHF", "📊", "#3498db")
        self.card_savings = CompactKPICard("Ersparnis", "0 CHF", "🏦", "#9b59b6")
        
        kpi_layout.addWidget(self.card_income)
        kpi_layout.addWidget(self.card_expenses)
        kpi_layout.addWidget(self.card_balance)
        kpi_layout.addWidget(self.card_savings)
        layout.addWidget(self.kpi_widget)
        # Budget Progress
        self.budget_group = QGroupBox("📈 Budget vs. Ist")
        budget_layout = QVBoxLayout(self.budget_group)
        budget_layout.setSpacing(6)

        # Subtabs: Kurz / Tabellarisch
        self.budget_tabs = QTabWidget()

        # --- Kurz (Progress Bars)
        progress_widget = QWidget()
        p_layout = QVBoxLayout(progress_widget)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(4)

        self.pb_income = CompactProgressBar("Einkommen", 1000)
        self.pb_expenses = CompactProgressBar("Ausgaben", 1000)
        self.pb_savings = CompactProgressBar("Ersparnis", 1000)

        p_layout.addWidget(self.pb_income)
        p_layout.addWidget(self.pb_expenses)
        p_layout.addWidget(self.pb_savings)
        self.budget_tabs.addTab(progress_widget, "Kurz")

        # --- Tabellarisch (mehrere Monate)
        table_widget = QWidget()
        t_layout = QVBoxLayout(table_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(6)

        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 0, 0, 0)
        ctrl.setSpacing(8)
        ctrl.addWidget(QLabel("Monate:"))
        self.month_window_combo = QComboBox()
        self.month_window_combo.addItems([
            "Auswahl (1 Monat)",
            "Aktueller + nächster",
            "Letzte 2 + aktueller",
            "Letzte 3 + aktueller",
        ])
        self.month_window_combo.setCurrentIndex(2)
        ctrl.addWidget(self.month_window_combo)
        ctrl.addStretch()
        t_layout.addLayout(ctrl)

        self.tbl_budget_table = QTableWidget()
        self.tbl_budget_table.setColumnCount(0)
        self.tbl_budget_table.setRowCount(0)
        self.tbl_budget_table.setAlternatingRowColors(True)
        self.tbl_budget_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_budget_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tbl_budget_table.verticalHeader().setVisible(False)
        t_layout.addWidget(self.tbl_budget_table)

        self.budget_tabs.addTab(table_widget, "Tabellarisch")

        budget_layout.addWidget(self.budget_tabs)
        layout.addWidget(self.budget_group)

        # Charts
        self.chart_tabs = QTabWidget()
        self.chart_tabs.setMaximumHeight(320)
        
        cat_widget = QWidget()
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_categories = CompactChart()
        cat_layout.addWidget(self.chart_categories)
        self.chart_tabs.addTab(cat_widget, "📊 Kategorien")
        
        typ_widget = QWidget()
        typ_layout = QVBoxLayout(typ_widget)
        typ_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_types = CompactChart()
        typ_layout.addWidget(self.chart_types)
        self.chart_tabs.addTab(typ_widget, "📈 Verteilung")
        
        layout.addWidget(self.chart_tabs)
        layout.addStretch()
        
        return widget

    def _create_right_panel(self) -> QWidget:
        """Rechtes Panel: Filter & Transaktionen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.right_tabs = QTabWidget()
        
        filter_widget = self._create_filter_panel()
        self.right_tabs.addTab(filter_widget, "🔍 Filter")
        
        trans_widget = self._create_transactions_panel()
        self.right_tabs.addTab(trans_widget, "📋 Transaktionen")
        
        layout.addWidget(self.right_tabs)
        return widget

    def _create_filter_panel(self) -> QWidget:
        """Filter-Panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)
        
        # Datumsbereich
        form.addWidget(QLabel("Von:"), 0, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(_to_qdate(date.today() - timedelta(days=30)))
        form.addWidget(self.date_from, 0, 1)

        form.addWidget(QLabel("Bis:"), 1, 0)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(_to_qdate(date.today()))
        form.addWidget(self.date_to, 1, 1)

        # Typ & Kategorie
        form.addWidget(QLabel("Typ:"), 2, 0)
        self.typ_combo = QComboBox()
        self.typ_combo.addItems(TYPES)
        form.addWidget(self.typ_combo, 2, 1)

        form.addWidget(QLabel("Kategorie:"), 3, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItem("Alle Kategorien")
        form.addWidget(self.category_combo, 3, 1)

        # Tag
        form.addWidget(QLabel("Tag:"), 4, 0)
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("Alle Tags")
        form.addWidget(self.tag_combo, 4, 1)

        # Suche
        form.addWidget(QLabel("Suche:"), 5, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Beschreibung...")
        form.addWidget(self.search_edit, 5, 1)

        # Betragsfilter
        form.addWidget(QLabel("Min CHF:"), 6, 0)
        self.min_amount = QLineEdit()
        self.min_amount.setPlaceholderText("0")
        self.min_amount.setValidator(QDoubleValidator(0.0, 1e12, 2, self))
        form.addWidget(self.min_amount, 6, 1)

        form.addWidget(QLabel("Max CHF:"), 7, 0)
        self.max_amount = QLineEdit()
        self.max_amount.setPlaceholderText("∞")
        self.max_amount.setValidator(QDoubleValidator(0.0, 1e12, 2, self))
        form.addWidget(self.max_amount, 7, 1)

        # Checkboxen
        self.only_fix = QCheckBox("Nur Fixkosten")
        form.addWidget(self.only_fix, 8, 0, 1, 2)
        
        self.only_recurring = QCheckBox("Nur wiederkehrend")
        form.addWidget(self.only_recurring, 9, 0, 1, 2)

        # Limit
        form.addWidget(QLabel("Limit:"), 10, 0)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 500)
        self.limit_spin.setValue(50)
        form.addWidget(self.limit_spin, 10, 1)

        layout.addLayout(form)

        # Reset Button
        self.btn_reset_filters = QPushButton("🔄 Filter zurücksetzen")
        layout.addWidget(self.btn_reset_filters)
        
        layout.addStretch()
        return widget

    def _create_transactions_panel(self) -> QWidget:
        """Transaktions-Tabelle"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.lbl_count = QLabel("0 Transaktionen")
        self.lbl_count.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_count)

        self.tbl_transactions = QTableWidget()
        self.tbl_transactions.setColumnCount(6)
        self.tbl_transactions.setHorizontalHeaderLabels([
            "Datum", "Typ", "Kategorie", "Betrag", "Beschreibung", "Tags"
        ])
        
        header = self.tbl_transactions.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        
        self.tbl_transactions.setColumnWidth(0, 80)
        self.tbl_transactions.setColumnWidth(1, 75)
        self.tbl_transactions.setColumnWidth(2, 110)
        self.tbl_transactions.setColumnWidth(3, 90)
        self.tbl_transactions.setColumnWidth(5, 70)
        
        self.tbl_transactions.setAlternatingRowColors(True)
        self.tbl_transactions.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_transactions.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_transactions.verticalHeader().setVisible(False)
        
        layout.addWidget(self.tbl_transactions)
        return widget

    # ========== Signals ==========
    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset_filters.clicked.connect(self._reset_filters)
        
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)
        self.year_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.month_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.month_combo.currentIndexChanged.connect(self._sync_month_window_enabled)
        if hasattr(self, 'month_window_combo'):
            self.month_window_combo.currentIndexChanged.connect(self._delayed_refresh)
        
        self.date_from.dateChanged.connect(self._delayed_refresh)
        self.date_to.dateChanged.connect(self._delayed_refresh)
        self.typ_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.category_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.tag_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.search_edit.textChanged.connect(self._delayed_refresh)
        self.min_amount.textChanged.connect(self._delayed_refresh)
        self.max_amount.textChanged.connect(self._delayed_refresh)
        self.only_fix.stateChanged.connect(self._delayed_refresh)
        self.only_recurring.stateChanged.connect(self._delayed_refresh)
        self.limit_spin.valueChanged.connect(self._delayed_refresh)
        
        # KPI Card Clicks
        self.card_income.clicked.connect(lambda: self._filter_by_typ("Einkommen"))
        self.card_expenses.clicked.connect(lambda: self._filter_by_typ("Ausgaben"))
        self.card_savings.clicked.connect(lambda: self._filter_by_typ("Ersparnisse"))
        self.card_balance.clicked.connect(lambda: self._filter_by_typ("Alle"))

    def _filter_by_typ(self, typ: str):
        """Filtert nach Typ wenn auf KPI geklickt wird"""
        idx = self.typ_combo.findText(typ)
        if idx >= 0:
            self.typ_combo.setCurrentIndex(idx)
        # Wechsle zu Transaktionen-Tab
        self.right_tabs.setCurrentIndex(1)

    # ========== Data Loading ==========
    def _reload_years(self):
        self.year_combo.clear()
        years = self.track.get_available_years()
        if not years:
            years = [date.today().year]
        for y in years:
            self.year_combo.addItem(str(y))
        cy = date.today().year
        idx = years.index(cy) if cy in years else 0
        self.year_combo.setCurrentIndex(idx)

    def _on_range_changed(self):
        idx = self.range_combo.currentIndex()
        is_custom = (idx == 4)
        is_year_month = (idx == 0)
        
        self.year_combo.setEnabled(is_year_month)
        self.month_combo.setEnabled(is_year_month)
        if hasattr(self, 'month_window_combo'):
            self.month_window_combo.setEnabled(is_year_month and self.month_combo.currentIndex() != 0)
        self.date_from.setEnabled(is_custom)
        self.date_to.setEnabled(is_custom)
        
        today = date.today()
        if idx == 1:
            self.date_from.setDate(_to_qdate(today - timedelta(days=7)))
            self.date_to.setDate(_to_qdate(today))
        elif idx == 2:
            self.date_from.setDate(_to_qdate(today - timedelta(days=30)))
            self.date_to.setDate(_to_qdate(today))
        elif idx == 3:
            self.date_from.setDate(_to_qdate(today - timedelta(days=90)))
            self.date_to.setDate(_to_qdate(today))
        
        self._delayed_refresh()


    def _sync_month_window_enabled(self):
        # Monatsfenster ist nur sinnvoll im Modus "Jahr/Monat" und wenn ein Monat ausgewählt ist.
        is_year_month = (self.range_combo.currentIndex() == 0)
        if hasattr(self, 'month_window_combo'):
            self.month_window_combo.setEnabled(is_year_month and self.month_combo.currentIndex() != 0)

    def _reset_filters(self):
        self.range_combo.setCurrentIndex(0)
        self.typ_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.tag_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self.min_amount.clear()
        self.max_amount.clear()
        self.only_fix.setChecked(False)
        self.only_recurring.setChecked(False)
        self.limit_spin.setValue(50)
        self.refresh_data()

    def _delayed_refresh(self):
        self._refresh_timer.stop()
        self._refresh_timer.start(250)

    def refresh_data(self):
        """Hauptmethode zum Aktualisieren"""
        self._load_categories()
        self._load_tags()
        
        date_from, date_to = self._get_date_range()
        
        self._load_kpis(date_from, date_to)
        self._load_budget_progress(date_from, date_to)
        self._load_budget_table(date_from, date_to)
        self._load_charts(date_from, date_to)
        self._load_transactions(date_from, date_to)

    def _get_date_range(self) -> tuple[date, date]:
        idx = self.range_combo.currentIndex()
        
        if idx == 0:  # Jahr/Monat
            try:
                year = int(self.year_combo.currentText())
                month_idx = self.month_combo.currentIndex()
                if month_idx == 0:
                    return (date(year, 1, 1), date(year, 12, 31))
                else:
                    return _month_range(year, month_idx)
            except:
                pass
        
        d_from = self.date_from.date()
        d_to = self.date_to.date()
        return (date(d_from.year(), d_from.month(), d_from.day()),
                date(d_to.year(), d_to.month(), d_to.day()))

    def _load_categories(self):
        current = self.category_combo.currentText()
        blocker = QSignalBlocker(self.category_combo)
        self.category_combo.clear()
        self.category_combo.addItem("Alle Kategorien")

        cats = self.categories.get_all_categories()

        # Tree-Cache
        self._cat_name_to_id = {}
        self._cat_children = {}
        self._cat_id_to_name_typ = {}

        for c in cats:
            cid = int(c["id"])
            typ = str(c.get("typ") or "")
            name = str(c.get("name") or "")
            parent_id = c.get("parent_id")
            parent_id = int(parent_id) if parent_id is not None else None

            self._cat_name_to_id[(typ, name)] = cid
            self._cat_id_to_name_typ[cid] = (typ, name)
            self._cat_children.setdefault(cid, [])
            if parent_id is not None:
                self._cat_children.setdefault(parent_id, []).append(cid)

        for c in cats:
            self.category_combo.addItem(c["name"])

        idx = self.category_combo.findText(current)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        del blocker
        self._descendant_name_cache = {}

    def _load_tags(self):
        current = self.tag_combo.currentText()
        blocker = QSignalBlocker(self.tag_combo)
        self.tag_combo.clear()
        self.tag_combo.addItem("Alle Tags")
        
        self._tag_name_to_id = {}
        tags = self.tags.get_all_tags()
        for tag in tags:
            name = tag["name"]
            self.tag_combo.addItem(name)
            self._tag_name_to_id[name] = tag["id"]
        
        idx = self.tag_combo.findText(current)
        if idx >= 0:
            self.tag_combo.setCurrentIndex(idx)
        del blocker

    def _load_kpis(self, date_from: date, date_to: date):
        rows = self.track.get_entries_in_range(date_from, date_to)

        total_income = sum(r.amount for r in rows if _norm_typ(r.typ) == "Einkommen")
        total_expenses = sum(abs(r.amount) for r in rows if _norm_typ(r.typ) == "Ausgaben")
        total_savings = sum(r.amount for r in rows if _norm_typ(r.typ) == "Ersparnisse")
        balance = total_income - total_expenses
        
        self.card_income.update_value(format_chf(total_income))
        self.card_expenses.update_value(format_chf(total_expenses))
        self.card_savings.update_value(format_chf(total_savings))
        
        # Bilanz-Farbe
        balance_color = "#27ae60" if balance >= 0 else "#e74c3c"
        self.card_balance.update_value(format_chf(balance), balance_color)

    def _load_budget_progress(self, date_from: date, date_to: date):
        """Lädt Budget vs. Ist-Vergleich"""
        try:
            year = date_from.year
            month = date_from.month if date_from.month == date_to.month else None
            
            # Budget-Summen holen (korrigierte Methode!)
            budget_sums = self.budget.sum_by_typ(year, month)
            
            budget_income = budget_sums.get("Einkommen", 0)
            budget_expenses = budget_sums.get("Ausgaben", 0)
            budget_savings = budget_sums.get("Ersparnisse", 0)
            
        except Exception as e:
            budget_income = 0
            budget_expenses = 0
            budget_savings = 0
        
        # Ist-Werte
        rows = self.track.get_entries_in_range(date_from, date_to)
        actual_income = sum(r.amount for r in rows if _norm_typ(r.typ) == "Einkommen")
        actual_expenses = sum(abs(r.amount) for r in rows if _norm_typ(r.typ) == "Ausgaben")
        actual_savings = sum(r.amount for r in rows if _norm_typ(r.typ) == "Ersparnisse")
        
        self.pb_income.set_values(actual_income, budget_income)
        self.pb_expenses.set_values(actual_expenses, budget_expenses)
        self.pb_savings.set_values(actual_savings, budget_savings)


    def _load_budget_table(self, date_from: date, date_to: date):
        """Tabellarische Budget-Übersicht (Budget / Ist / Rest) über mehrere Monate."""
        if not hasattr(self, "tbl_budget_table"):
            return

        # UI-Enable sync
        self._sync_month_window_enabled()

        # --- Monate bestimmen ---
        months: list[tuple[int, int]] = []
        try:
            if self.range_combo.currentIndex() == 0:  # Jahr/Monat
                year = int(self.year_combo.currentText())
                m_idx = int(self.month_combo.currentIndex())

                if m_idx == 0:  # Gesamtes Jahr
                    months = [(year, m) for m in range(1, 13)]
                else:
                    mode = int(self.month_window_combo.currentIndex()) if hasattr(self, "month_window_combo") else 0
                    if mode == 0:  # Auswahl
                        months = [(year, m_idx)]
                    elif mode == 1:  # Aktuell + nächster
                        months = [(year, m_idx)]
                        if m_idx < 12:
                            months.append((year, m_idx + 1))
                    elif mode == 2:  # Letzte 2 + aktueller
                        start = max(1, m_idx - 2)
                        months = [(year, m) for m in range(start, m_idx + 1)]
                    else:  # Letzte 3 + aktueller
                        start = max(1, m_idx - 3)
                        months = [(year, m) for m in range(start, m_idx + 1)]
            else:
                # Custom range: Monate zwischen date_from und date_to
                cur = date(date_from.year, date_from.month, 1)
                end = date(date_to.year, date_to.month, 1)
                while cur <= end:
                    months.append((cur.year, cur.month))
                    if cur.month == 12:
                        cur = date(cur.year + 1, 1, 1)
                    else:
                        cur = date(cur.year, cur.month + 1, 1)
        except Exception:
            months = [(date_from.year, date_from.month)]

        if not months:
            months = [(date_from.year, date_from.month)]

        years_in_months = {y for y, _ in months}
        same_year = len(years_in_months) == 1
        headers = [(MONTHS[m], y) for (y, m) in months]
        col_labels = [mn if same_year else f"{mn} {y}" for (mn, y) in headers]

        # --- Tabelle initialisieren ---
        row_labels = ["Einkommen", "Ausgaben", "Ersparnisse"]
        self.tbl_budget_table.clear()
        self.tbl_budget_table.setRowCount(len(row_labels))
        self.tbl_budget_table.setColumnCount(len(months))
        self.tbl_budget_table.setHorizontalHeaderLabels(col_labels)
        self.tbl_budget_table.setVerticalHeaderLabels(row_labels)

        self.tbl_budget_table.verticalHeader().setVisible(True)
        self.tbl_budget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_budget_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # --- Werte berechnen ---
        for r_i, typ in enumerate(row_labels):
            for c_i, (y, m) in enumerate(months):
                # Budget (Summe)
                try:
                    bsum = float(self.budget.sum_by_typ(y, m).get(typ, 0.0))
                except Exception:
                    bsum = 0.0

                # Ist (Tracking) im Monatsbereich
                d1, d2 = _month_range(y, m)
                trows = self.track.get_entries_in_range(d1, d2)

                if typ == "Einkommen":
                    asum = sum(rr.amount for rr in trows if _norm_typ(rr.typ) == typ)
                    rest = asum - bsum  # positiver = über Plan
                elif typ == "Ausgaben":
                    asum = sum(abs(rr.amount) for rr in trows if _norm_typ(rr.typ) == typ)
                    rest = bsum - asum  # positiver = Budget übrig
                else:  # Ersparnisse
                    asum = sum(rr.amount for rr in trows if _norm_typ(rr.typ) == typ)
                    rest = bsum - asum  # positiver = noch zu sparen

                cell_text = f"B: {format_chf(bsum)}\nI: {format_chf(asum)}\nR: {format_chf(rest)}"
                it = QTableWidgetItem(cell_text)
                it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                it.setToolTip(
                    f"{typ} – {col_labels[c_i]}\n"
                    f"Budget: {format_chf(bsum)}\n"
                    f"Ist: {format_chf(asum)}\n"
                    f"Rest: {format_chf(rest)}"
                )

                # leichte Hervorhebung bei negativem Rest
                if rest < 0:
                    it.setForeground(QColor("#e74c3c"))

                self.tbl_budget_table.setItem(r_i, c_i, it)


    def _load_charts(self, date_from: date, date_to: date):
        rows = self.track.get_entries_in_range(date_from, date_to)
        
        # Kategorien-Chart (nur Ausgaben)
        cat_data = {}
        for r in rows:
            if _norm_typ(r.typ) == "Ausgaben":
                cat_data[r.category] = cat_data.get(r.category, 0) + abs(r.amount)
        
        self.chart_categories.create_pie_chart(cat_data, "Ausgaben nach Kategorie")
        
        # Typ-Chart
        typ_data = {
            "Einkommen": sum(r.amount for r in rows if _norm_typ(r.typ) == "Einkommen"),
            "Ausgaben": sum(abs(r.amount) for r in rows if _norm_typ(r.typ) == "Ausgaben"),
            "Ersparnisse": sum(r.amount for r in rows if _norm_typ(r.typ) == "Ersparnisse"),
        }
        typ_data = {k: v for k, v in typ_data.items() if v > 0}
        
        self.chart_types.create_pie_chart(typ_data, "Verteilung nach Typ")

    def _get_descendant_names(self, typ: str, selected_name: str) -> set[str]:
        """Gibt Namen der Kategorie + alle Unterkategorien zurück."""
        if not selected_name:
            return set()
        
        key = (typ, selected_name)
        cache = getattr(self, "_descendant_name_cache", {})
        if key in cache:
            return set(cache[key])

        start = self._cat_name_to_id.get(key)
        if start is None:
            return {selected_name}

        out_ids = [start]
        i = 0
        while i < len(out_ids):
            cid = out_ids[i]
            for ch in self._cat_children.get(cid, []):
                if ch not in out_ids:
                    out_ids.append(ch)
            i += 1

        names = {self._cat_id_to_name_typ[cid][1] for cid in out_ids if cid in self._cat_id_to_name_typ}
        self._descendant_name_cache[key] = names
        return names

    def _load_transactions(self, date_from: date, date_to: date):
        typ_filter = self.typ_combo.currentText()
        cat_filter = self.category_combo.currentText()
        tag_filter = self.tag_combo.currentText()
        search_text = self.search_edit.text().strip().lower()
        
        try:
            min_amt = float(self.min_amount.text()) if self.min_amount.text() else None
        except:
            min_amt = None
        
        try:
            max_amt = float(self.max_amount.text()) if self.max_amount.text() else None
        except:
            max_amt = None
        
        only_fix = self.only_fix.isChecked()
        only_rec = self.only_recurring.isChecked()
        limit = self.limit_spin.value()
        
        rows = self.track.get_entries_in_range(date_from, date_to)
        
        filtered = []
        for r in rows:
            if typ_filter != "Alle" and _norm_typ(r.typ) != typ_filter:
                continue
            
            if cat_filter != "Alle Kategorien":
                allowed = self._get_descendant_names(r.typ, cat_filter)
                if allowed and r.category not in allowed:
                    continue
            
            if tag_filter != "Alle Tags":
                tag_id = self._tag_name_to_id.get(tag_filter)
                if tag_id:
                    entry_tags = self.tags.get_tags_for_entry(r.id)
                    if tag_id not in [t["id"] for t in entry_tags]:
                        continue
            
            if search_text and search_text not in r.description.lower():
                continue
            
            amt = abs(r.amount)
            if min_amt is not None and amt < min_amt:
                continue
            if max_amt is not None and amt > max_amt:
                continue
            
            if only_fix or only_rec:
                try:
                    is_fix, is_rec, _day = self.categories.get_flags(r.typ, r.category)
                    if only_fix and not is_fix:
                        continue
                    if only_rec and not is_rec:
                        continue
                except:
                    continue

            filtered.append(r)
        
        filtered = filtered[:limit]
        self._display_transactions(filtered)
        self.lbl_count.setText(f"{len(filtered)} Transaktionen (max {limit})")

    def _display_transactions(self, rows: list[TrackingRow]):
        self.tbl_transactions.setRowCount(len(rows))
        
        for i, r in enumerate(rows):
            self.tbl_transactions.setItem(i, 0, QTableWidgetItem(str(r.date)))
            self.tbl_transactions.setItem(i, 1, QTableWidgetItem(r.typ))
            self.tbl_transactions.setItem(i, 2, QTableWidgetItem(r.category))
            
            amt_item = QTableWidgetItem(format_chf(r.amount))
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_transactions.setItem(i, 3, amt_item)
            
            self.tbl_transactions.setItem(i, 4, QTableWidgetItem(r.description))
            
            try:
                tags = self.tags.get_tags_for_entry(r.id)
                tag_names = ", ".join(t["name"] for t in tags)
            except:
                tag_names = ""
            self.tbl_transactions.setItem(i, 5, QTableWidgetItem(tag_names))
