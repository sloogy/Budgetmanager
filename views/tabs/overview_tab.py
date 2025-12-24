from __future__ import annotations

import sqlite3
from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QGroupBox,
    QTabWidget, QFrame, QScrollArea, QPushButton, QCheckBox
)

from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QLineSeries, 
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
    QHorizontalBarSeries
)
from PySide6.QtGui import QPainter, QFont, QColor

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from views.delegates.badge_delegate import BadgeDelegate
from settings import Settings

MONTHS = ["Gesamtes Jahr","Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
MONTH_NAMES_SHORT = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

def chf(x: float) -> str:
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ".").replace("X", "'")

class KPIWidget(QFrame):
    """Großes Widget für eine Kennzahl"""
    def __init__(self, label: str, value: str, color: str = "#2196F3"):
        super().__init__()
        self.settings = Settings()
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)
        
        layout = QVBoxLayout()
        
        # Label
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setObjectName("kpi_label")  # Für Theme-Styling
        
        # Wert
        val = QLabel(value)
        val.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        val.setFont(font)
        val.setStyleSheet(f"color: {color};")
        
        layout.addWidget(lbl)
        layout.addWidget(val)
        self.setLayout(layout)
        
        self.value_label = val
        self.label_widget = lbl
    
    def update_value(self, value: str):
        self.value_label.setText(value)

class OverviewTab(QWidget):
    def __init__(self, conn: sqlite3.Connection):
        self.settings = Settings()
        super().__init__()
        self.conn = conn
        self.budget = BudgetModel(conn)
        self.track = TrackingModel(conn)

        # === FILTER ===
        self.year = QComboBox()
        self._reload_years()

        self.month = QComboBox()
        self.month.addItems(MONTHS)

        self.typ = QComboBox()
        self.typ.addItems(["Alle","Ausgaben","Einkommen","Ersparnisse"])

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Jahr:"))
        filter_layout.addWidget(self.year)
        filter_layout.addWidget(QLabel("Monat:"))
        filter_layout.addWidget(self.month)
        filter_layout.addWidget(QLabel("Ansicht:"))
        filter_layout.addWidget(self.typ)
        filter_layout.addStretch(1)

        # === KPIs (Kennzahlen) ===
        self.kpi_einkommen = KPIWidget("Einkommen", "CHF 0", "#4CAF50")
        self.kpi_ausgaben = KPIWidget("Ausgaben", "CHF 0", "#f44336")
        self.kpi_ersparnisse = KPIWidget("Ersparnisse", "CHF 0", "#FF9800")
        self.kpi_saldo = KPIWidget("Saldo", "CHF 0", "#2196F3")
        self.kpi_sparquote = KPIWidget("Sparquote", "0%", "#9C27B0")

        kpi_layout = QHBoxLayout()
        kpi_layout.addWidget(self.kpi_einkommen)
        kpi_layout.addWidget(self.kpi_ausgaben)
        kpi_layout.addWidget(self.kpi_ersparnisse)
        kpi_layout.addWidget(self.kpi_saldo)
        kpi_layout.addWidget(self.kpi_sparquote)

        # === TAB WIDGET für verschiedene Ansichten ===
        self.tabs = QTabWidget()
        
        # Tab 1: Dashboard (Übersicht)
        dashboard = self._create_dashboard_tab()
        self.tabs.addTab(dashboard, "📊 Dashboard")
        
        # Tab 2: Detailvergleich
        compare = self._create_compare_tab()
        self.tabs.addTab(compare, "📋 Budget vs. Tracking")
        
        # Tab 3: Zeitverlauf
        timeline = self._create_timeline_tab()
        self.tabs.addTab(timeline, "📈 Verlauf")
        
        # Tab 4: Top-Kategorien
        ranking = self._create_ranking_tab()
        self.tabs.addTab(ranking, "🏆 Top-Kategorien")
        
        # Tab 5: Prognose & Analyse (NEU)
        forecast = self._create_forecast_tab()
        self.tabs.addTab(forecast, "🔮 Prognose")
        
        # Tab 6: Jahresvergleich (NEU)
        comparison = self._create_year_comparison_tab()
        self.tabs.addTab(comparison, "📅 Jahresvergleich")

        # === HAUPTLAYOUT ===
        main_layout = QVBoxLayout()
        main_layout.addLayout(filter_layout)
        main_layout.addLayout(kpi_layout)
        main_layout.addWidget(self.tabs)
        
        self.setLayout(main_layout)

        # === SIGNALS ===
        self.year.currentIndexChanged.connect(lambda _: self._on_year_changed())
        self.month.currentIndexChanged.connect(lambda _: self.refresh())
        self.typ.currentIndexChanged.connect(lambda _: self.refresh())

        self._on_year_changed()

    def _create_dashboard_tab(self) -> QWidget:
        """Tab 1: Hauptübersicht mit Pie/Bar Charts"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Chart-Typ Umschalter
        chart_toggle = QHBoxLayout()
        self.btn_pie_chart = QPushButton("🥧 Kreisdiagramm")
        self.btn_pie_chart.setCheckable(True)
        self.btn_pie_chart.setChecked(True)
        self.btn_pie_chart.clicked.connect(lambda: self._toggle_chart_type("pie"))
        
        self.btn_bar_chart = QPushButton("📊 Balkendiagramm")
        self.btn_bar_chart.setCheckable(True)
        self.btn_bar_chart.clicked.connect(lambda: self._toggle_chart_type("bar"))
        
        self.btn_hbar_chart = QPushButton("📉 Horizontale Balken")
        self.btn_hbar_chart.setCheckable(True)
        self.btn_hbar_chart.clicked.connect(lambda: self._toggle_chart_type("hbar"))
        
        chart_toggle.addWidget(QLabel("Diagrammtyp:"))
        chart_toggle.addWidget(self.btn_pie_chart)
        chart_toggle.addWidget(self.btn_bar_chart)
        chart_toggle.addWidget(self.btn_hbar_chart)
        chart_toggle.addStretch()
        
        layout.addLayout(chart_toggle)
        
        # Charts nebeneinander
        self.chart_budget = QChartView()
        self.chart_track = QChartView()
        self.current_chart_type = "pie"
        
        charts_row = QHBoxLayout()
        charts_row.addWidget(self._box("💰 Geplant (Budget)", self.chart_budget))
        charts_row.addWidget(self._box("💳 Tatsächlich (Tracking)", self.chart_track))
        
        # Schnellstatistik-Tabelle
        self.stats_table = QTableWidget(0, 3)
        self.stats_table.setHorizontalHeaderLabels(["Kategorie", "Budget", "Getrackt"])
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setMaximumHeight(200)
        
        layout.addLayout(charts_row, 2)
        layout.addWidget(self._box("📊 Zusammenfassung", self.stats_table), 1)
        
        widget.setLayout(layout)
        return widget
    
    def _toggle_chart_type(self, chart_type: str):
        """Wechselt den Diagrammtyp"""
        self.current_chart_type = chart_type
        
        # Button-Status aktualisieren
        self.btn_pie_chart.setChecked(chart_type == "pie")
        self.btn_bar_chart.setChecked(chart_type == "bar")
        self.btn_hbar_chart.setChecked(chart_type == "hbar")
        
        # Charts neu zeichnen
        self.refresh()

    def _create_compare_tab(self) -> QWidget:
        """Tab 2: Detaillierter Budget vs. Tracking Vergleich"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Typ","Kategorie","Budget","Getrackt","Differenz","%"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Info-Label
        info = QLabel("💡 Grün = unter Budget | Rot = über Budget | % = Ausnutzung des Budgets")
        info.setObjectName("info_label")
        
        layout.addWidget(info)
        layout.addWidget(self.table)
        
        widget.setLayout(layout)
        return widget

    def _create_timeline_tab(self) -> QWidget:
        """Tab 3: Zeitlicher Verlauf"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Line Chart
        self.chart_line = QChartView()
        
        # Bar Chart für Monatssummen
        self.chart_bar = QChartView()
        
        layout.addWidget(self._box("📈 Monatsverlauf (Linie)", self.chart_line), 1)
        layout.addWidget(self._box("📊 Monatsvergleich (Balken)", self.chart_bar), 1)
        
        widget.setLayout(layout)
        return widget

    def _create_ranking_tab(self) -> QWidget:
        """Tab 4: Top-Kategorien Rankings"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Zwei Tabellen: Größte Ausgaben und Größte Transaktionen
        self.rank = QTableWidget(0, 4)
        self.rank.setHorizontalHeaderLabels(["Typ","Kategorie","Betrag","% vom Total"])
        # Badge/Pillen Darstellung für Typ-Spalte
        self._rank_badge_delegate = BadgeDelegate(self.rank, color_map=getattr(self, "settings", Settings()).get("type_colors", {}))
        self.rank.setItemDelegateForColumn(0, self._rank_badge_delegate)
        self.rank.setColumnWidth(0, 120)
        self.rank.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rank.setAlternatingRowColors(True)

        self.last = QTableWidget(0, 5)
        self.last.setHorizontalHeaderLabels(["Datum","Typ","Kategorie","Betrag","Details"])
        self.last.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.last.setAlternatingRowColors(True)
        
        layout.addWidget(self._box("🏆 Top 20 Kategorien (nach Betrag)", self.rank), 1)
        layout.addWidget(self._box("💎 Größte Einzeltransaktionen", self.last), 1)
        
        widget.setLayout(layout)
        return widget

    def _box(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout()
        lay.addWidget(widget)
        box.setLayout(lay)
        return box

    def _reload_years(self):
        from datetime import date
        current_year = date.today().year
        
        years = sorted(set(self.budget.years()) | set(self.track.years()))
        self.year.clear()
        self.year.addItem("Gesamter Zeitraum")
        for y in years:
            self.year.addItem(str(y))
        
        # Automatisch aktuelles Jahr wählen (falls vorhanden)
        if years:
            if current_year in years:
                self.year.setCurrentText(str(current_year))
            else:
                # Aktuelles Jahr nicht in DB -> neuestes Jahr wählen
                self.year.setCurrentText(str(years[-1]))

    def _get_selected_year(self) -> int | None:
        txt = self.year.currentText()
        if txt == "Gesamter Zeitraum":
            return None
        try:
            return int(txt)
        except Exception:
            return None

    def _on_year_changed(self):
        if self._get_selected_year() is None:
            self.month.setCurrentIndex(0)
            self.month.setEnabled(False)
        else:
            self.month.setEnabled(True)
        self.refresh()

    def refresh(self):
        year = self._get_selected_year()
        month_idx = int(self.month.currentIndex())
        month = None if (month_idx == 0) else month_idx
        typ_filter = self.typ.currentText()
        typ = None if typ_filter == "Alle" else typ_filter

        # Budget und Tracking Daten holen
        if year is None:
            b_typ = self.budget.sum_by_typ_all(month=None)
            t_typ = self.track.sum_by_typ(year=None, month=None)
        else:
            b_typ = self.budget.sum_by_typ(year, month=month)
            t_typ = self.track.sum_by_typ(year=year, month=month)

        # KPIs aktualisieren
        self._update_kpis(b_typ, t_typ)

        # Dashboard Charts aktualisieren (mit Chart-Typ-Toggle)
        self._set_dashboard_charts(b_typ, "Budget", self.chart_budget)
        self._set_dashboard_charts(t_typ, "Tracking", self.chart_track)

        # Line Chart
        if year is None:
            self._set_line_all(self.chart_line, typ)
            self._set_bar_all(self.chart_bar, typ)
        else:
            self._set_line_year(self.chart_line, year, typ)
            self._set_bar_year(self.chart_bar, year, typ)

        # Tabellen aktualisieren
        self._fill_stats_table(b_typ, t_typ)
        self._fill_compare_table(year, month, typ)
        self._fill_ranking(year, month, typ)
        self._fill_last()
        
        # Prognose aktualisieren (nur wenn Jahr ausgewählt)
        if year is not None:
            self._update_forecast(year)

    def _update_kpis(self, budget: dict[str, float], tracking: dict[str, float]):
        """Aktualisiert die großen Kennzahlen oben"""
        b_eink = budget.get("Einkommen", 0.0)
        b_ausg = budget.get("Ausgaben", 0.0)
        b_ersp = budget.get("Ersparnisse", 0.0)
        
        t_eink = tracking.get("Einkommen", 0.0)
        t_ausg = tracking.get("Ausgaben", 0.0)
        t_ersp = tracking.get("Ersparnisse", 0.0)
        
        # Wir zeigen Tracking-Werte (tatsächlich)
        self.kpi_einkommen.update_value(f"CHF {chf(t_eink)}")
        self.kpi_ausgaben.update_value(f"CHF {chf(t_ausg)}")
        self.kpi_ersparnisse.update_value(f"CHF {chf(t_ersp)}")
        
        saldo = t_eink - t_ausg - t_ersp
        self.kpi_saldo.update_value(f"CHF {chf(saldo)}")
        
        # Sparquote = (Ersparnisse + Saldo) / Einkommen * 100
        if t_eink > 0:
            sparquote = ((t_ersp + saldo) / t_eink) * 100
            self.kpi_sparquote.update_value(f"{sparquote:.1f}%")
        else:
            self.kpi_sparquote.update_value("N/A")

    def _fill_stats_table(self, budget: dict[str, float], tracking: dict[str, float]):
        """Füllt die Zusammenfassungs-Tabelle im Dashboard"""
        self.stats_table.setRowCount(0)
        
        for typ in ["Einkommen", "Ausgaben", "Ersparnisse"]:
            b = budget.get(typ, 0.0)
            t = tracking.get(typ, 0.0)
            
            row = self.stats_table.rowCount()
            self.stats_table.insertRow(row)
            
            self.stats_table.setItem(row, 0, QTableWidgetItem(typ))
            
            itb = QTableWidgetItem(f"CHF {chf(b)}")
            itb.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stats_table.setItem(row, 1, itb)
            
            itt = QTableWidgetItem(f"CHF {chf(t)}")
            itt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stats_table.setItem(row, 2, itt)
        
        self.stats_table.resizeColumnsToContents()

    def _set_pie(self, view: QChartView, data: dict[str,float]):
        series = QPieSeries()
        total = sum(abs(float(v)) for v in data.values())
        if abs(total) < 1e-9:
            series.append("Keine Daten", 1.0)
        else:
            for k,v in data.items():
                slice = series.append(k, abs(float(v)))
                # Prozent im Label
                pct = (abs(float(v)) / total) * 100
                slice.setLabel(f"{k}: {pct:.1f}%")
        
        chart = QChart()
        chart.addSeries(series)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        view.setRenderHint(QPainter.Antialiasing, True)
        view.setChart(chart)

    def _set_line_year(self, view: QChartView, year: int, typ: str | None):
        b = self.budget.sum_by_month(year, typ=typ)
        t = self.track.sum_by_month(year, typ=typ)
        self._set_line_common(view, b, t, title=f"Verlauf {year}")

    def _set_line_all(self, view: QChartView, typ: str | None):
        b = self.budget.sum_by_month_all(typ=typ)
        t = self.track.sum_by_month_all(typ=typ)
        self._set_line_common(view, b, t, title="Gesamter Zeitraum (Monatsdurchschnitt)")

    def _set_line_common(self, view: QChartView, b: dict[int,float], t: dict[int,float], title: str):
        s_budget = QLineSeries()
        s_budget.setName("Budget")
        s_track = QLineSeries()
        s_track.setName("Getrackt")

        for m in range(1,13):
            s_budget.append(m, float(b.get(m,0.0)))
            s_track.append(m, float(t.get(m,0.0)))

        chart = QChart()
        chart.setTitle(title)
        chart.addSeries(s_budget)
        chart.addSeries(s_track)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.setAnimationOptions(QChart.SeriesAnimations)

        # X-Achse mit Monatsnamen
        ax_x = QBarCategoryAxis()
        ax_x.append(MONTH_NAMES_SHORT)
        ax_x.setTitleText("Monat")
        
        # Y-Achse
        ax_y = QValueAxis()
        vals = list(b.values()) + list(t.values())
        lo = min(vals) if vals else 0.0
        hi = max(vals) if vals else 1.0
        if abs(hi - lo) < 1e-9:
            hi = lo + 1.0
        ax_y.setRange(lo, hi)
        ax_y.setTitleText("CHF")

        chart.addAxis(ax_x, Qt.AlignBottom)
        chart.addAxis(ax_y, Qt.AlignLeft)
        s_budget.attachAxis(ax_x)
        s_budget.attachAxis(ax_y)
        s_track.attachAxis(ax_x)
        s_track.attachAxis(ax_y)

        view.setRenderHint(QPainter.Antialiasing, True)
        view.setChart(chart)

    def _set_bar_year(self, view: QChartView, year: int, typ: str | None):
        b = self.budget.sum_by_month(year, typ=typ)
        t = self.track.sum_by_month(year, typ=typ)
        self._set_bar_common(view, b, t, title=f"Monatssummen {year}")

    def _set_bar_all(self, view: QChartView, typ: str | None):
        b = self.budget.sum_by_month_all(typ=typ)
        t = self.track.sum_by_month_all(typ=typ)
        self._set_bar_common(view, b, t, title="Monatssummen (Durchschnitt)")

    def _set_bar_common(self, view: QChartView, b: dict[int,float], t: dict[int,float], title: str):
        set_budget = QBarSet("Budget")
        set_track = QBarSet("Getrackt")
        
        for m in range(1, 13):
            set_budget.append(float(b.get(m, 0.0)))
            set_track.append(float(t.get(m, 0.0)))
        
        series = QBarSeries()
        series.append(set_budget)
        series.append(set_track)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        categories = MONTH_NAMES_SHORT
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        vals = list(b.values()) + list(t.values())
        axis_y = QValueAxis()
        axis_y.setRange(0, max(vals) if vals else 1.0)
        axis_y.setTitleText("CHF")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        view.setRenderHint(QPainter.Antialiasing)
        view.setChart(chart)

    def _fill_compare_table(self, year:int|None, month:int|None, typ: str|None):
        self.table.setRowCount(0)
        typs = [typ] if typ else ["Ausgaben","Einkommen","Ersparnisse"]
        
        for t in typs:
            if year is None:
                bcat = self.budget.sum_by_category_all(t, month=None)
                tcat = self.track.sum_by_category(t, year=None, month=None)
            else:
                bcat = self.budget.sum_by_category(year, t, month=month)
                tcat = self.track.sum_by_category(t, year=year, month=month)
            
            all_cats = sorted(set(bcat.keys()) | set(tcat.keys()))
            for cat in all_cats:
                b0 = float(bcat.get(cat, 0.0))
                tr0 = float(tcat.get(cat, 0.0))
                diff = tr0 - b0
                pct = (abs(tr0)/abs(b0)*100.0) if abs(b0) > 1e-9 else (100.0 if abs(tr0)>1e-9 else 0.0)
                
                r = self.table.rowCount()
                self.table.insertRow(r)
                
                # Bestimme Farbe basierend auf Typ und Differenz
                row_color = None
                if t == "Ausgaben":
                    if diff < -1:  # Weniger ausgegeben als geplant (gut)
                        row_color = QColor(100, 200, 100)  # Grün
                    elif diff > 1:  # Mehr ausgegeben als geplant (schlecht)
                        row_color = QColor(255, 100, 100)  # Rot
                elif t == "Einkommen":
                    if diff > 1:  # Mehr eingenommen als geplant (gut)
                        row_color = QColor(100, 200, 100)  # Grün
                    elif diff < -1:  # Weniger eingenommen als geplant (schlecht)
                        row_color = QColor(255, 100, 100)  # Rot
                elif t == "Ersparnisse":
                    if diff < -1:  # Weniger gespart als geplant (schlecht)
                        row_color = QColor(255, 100, 100)  # Rot
                    elif diff > 1:  # Mehr gespart als geplant (gut)
                        row_color = QColor(100, 200, 100)  # Grün
                
                # Typ-Spalte
                it_typ = QTableWidgetItem(t)
                if row_color:
                    it_typ.setForeground(row_color)
                self.table.setItem(r, 0, it_typ)
                
                # Kategorie-Spalte
                it_cat = QTableWidgetItem(cat)
                if row_color:
                    it_cat.setForeground(row_color)
                self.table.setItem(r, 1, it_cat)
                
                # Budget-Spalte
                itb = QTableWidgetItem(f"CHF {chf(b0)}")
                itb.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                if row_color:
                    itb.setForeground(row_color)
                self.table.setItem(r, 2, itb)
                
                # Getrackt-Spalte
                itt = QTableWidgetItem(f"CHF {chf(tr0)}")
                itt.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                if row_color:
                    itt.setForeground(row_color)
                self.table.setItem(r, 3, itt)
                
                # Differenz-Spalte (immer farbig wenn relevant)
                itd = QTableWidgetItem(f"CHF {chf(diff)}")
                itd.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                if row_color:
                    itd.setForeground(row_color)
                self.table.setItem(r, 4, itd)
                
                # Prozent-Spalte
                itp = QTableWidgetItem(f"{pct:.0f}%")
                itp.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                if row_color:
                    itp.setForeground(row_color)
                self.table.setItem(r, 5, itp)
        
        self.table.resizeColumnsToContents()

    def _fill_ranking(self, year:int|None, month:int|None, typ: str|None):
        self.rank.setRowCount(0)
        typs = [typ] if typ else ["Ausgaben","Einkommen","Ersparnisse"]
        rows = []
        total_all = 0.0
        
        for t in typs:
            if year is None:
                tcat = self.track.sum_by_category(t, year=None, month=None)
            else:
                tcat = self.track.sum_by_category(t, year=year, month=month)
            
            for cat, tr in tcat.items():
                rows.append((abs(float(tr)), t, cat, float(tr)))
                total_all += abs(float(tr))
        
        rows.sort(reverse=True, key=lambda x: x[0])
        
        for abs_val, t, cat, tr in rows[:20]:  # Top 20
            r = self.rank.rowCount()
            self.rank.insertRow(r)
            self.rank.setItem(r,0,QTableWidgetItem(t))
            self.rank.setItem(r,1,QTableWidgetItem(cat))
            
            itt = QTableWidgetItem(f"CHF {chf(tr)}")
            itt.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.rank.setItem(r,2,itt)
            
            pct = (abs_val / total_all * 100) if total_all > 0 else 0
            itp = QTableWidgetItem(f"{pct:.1f}%")
            itp.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.rank.setItem(r,3,itp)
        
        self.rank.resizeColumnsToContents()

    def _fill_last(self):
        self.last.setRowCount(0)
        rows = self.track.last_n_by_abs_amount(10)  # Top 10 größte Transaktionen
        
        for r0 in rows:
            r = self.last.rowCount()
            self.last.insertRow(r)
            self.last.setItem(r,0,QTableWidgetItem(r0.d.strftime("%d.%m.%Y")))
            self.last.setItem(r,1,QTableWidgetItem(r0.typ))
            self.last.setItem(r,2,QTableWidgetItem(r0.category))
            
            it = QTableWidgetItem(f"CHF {chf(r0.amount)}")
            it.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.last.setItem(r,3,it)
            
            self.last.setItem(r,4,QTableWidgetItem(r0.details))
        
        self.last.resizeColumnsToContents()
    
    def _create_forecast_tab(self) -> QWidget:
        """Tab 5: Prognose & Analyse"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Prognose-Info
        info = QLabel("🔮 Hochrechnung basierend auf bisherigen Ausgaben/Einnahmen")
        info.setObjectName("info_label")
        layout.addWidget(info)
        
        # Prognose-Tabelle
        self.forecast_table = QTableWidget(0, 5)
        self.forecast_table.setHorizontalHeaderLabels([
            "Typ", "Bisher (Tracking)", "Budget (Jahr)", "Prognose (Jahr)", "Differenz"
        ])
        self.forecast_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.forecast_table.setAlternatingRowColors(True)
        
        layout.addWidget(self._box("📊 Jahresprognose", self.forecast_table))
        
        # Monats-Trend
        self.trend_chart = QChartView()
        layout.addWidget(self._box("📈 Ausgaben-Trend (Monatsdurchschnitt)", self.trend_chart))
        
        widget.setLayout(layout)
        return widget
    
    def _create_year_comparison_tab(self) -> QWidget:
        """Tab 6: Jahresvergleich"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Jahr-Auswahl für Vergleich
        compare_row = QHBoxLayout()
        compare_row.addWidget(QLabel("Vergleiche:"))
        
        self.compare_year1 = QComboBox()
        self.compare_year2 = QComboBox()
        
        years = sorted(set(self.budget.years()) | set(self.track.years()))
        for y in years:
            self.compare_year1.addItem(str(y))
            self.compare_year2.addItem(str(y))
        
        # Standard: Aktuelles Jahr vs. Vorjahr
        current_year = date.today().year
        if str(current_year) in [self.compare_year1.itemText(i) for i in range(self.compare_year1.count())]:
            self.compare_year1.setCurrentText(str(current_year))
        if str(current_year - 1) in [self.compare_year2.itemText(i) for i in range(self.compare_year2.count())]:
            self.compare_year2.setCurrentText(str(current_year - 1))
        
        compare_row.addWidget(self.compare_year1)
        compare_row.addWidget(QLabel("mit"))
        compare_row.addWidget(self.compare_year2)
        
        btn_compare = QPushButton("🔄 Vergleichen")
        btn_compare.clicked.connect(self._update_year_comparison)
        compare_row.addWidget(btn_compare)
        compare_row.addStretch()
        
        layout.addLayout(compare_row)
        
        # Vergleichs-Tabelle
        self.comparison_table = QTableWidget(0, 5)
        self.comparison_table.setHorizontalHeaderLabels([
            "Typ", "Jahr 1", "Jahr 2", "Differenz", "Änderung %"
        ])
        self.comparison_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.comparison_table.setAlternatingRowColors(True)
        
        layout.addWidget(self._box("📊 Jahresvergleich", self.comparison_table))
        
        # Vergleichs-Chart
        self.comparison_chart = QChartView()
        layout.addWidget(self._box("📈 Visueller Vergleich", self.comparison_chart))
        
        widget.setLayout(layout)
        return widget
    
    def _update_forecast(self, year: int | None):
        """Aktualisiert die Prognose-Tabelle"""
        if not hasattr(self, 'forecast_table'):
            return
            
        self.forecast_table.setRowCount(0)
        
        if year is None:
            return
        
        current_month = date.today().month
        months_passed = current_month
        months_remaining = 12 - current_month
        
        for typ in ["Einkommen", "Ausgaben", "Ersparnisse"]:
            # Bisher getrackt
            tracked = self.track.sum_by_typ(year=year, month=None).get(typ, 0)
            
            # Budget fürs Jahr
            budget = self.budget.sum_by_typ(year, month=None).get(typ, 0)
            
            # Prognose: (Bisherig / vergangene Monate) * 12
            if months_passed > 0:
                monthly_avg = tracked / months_passed
                forecast = monthly_avg * 12
            else:
                forecast = 0
            
            diff = forecast - budget
            
            r = self.forecast_table.rowCount()
            self.forecast_table.insertRow(r)
            
            self.forecast_table.setItem(r, 0, QTableWidgetItem(typ))
            
            it1 = QTableWidgetItem(f"CHF {chf(tracked)}")
            it1.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.forecast_table.setItem(r, 1, it1)
            
            it2 = QTableWidgetItem(f"CHF {chf(budget)}")
            it2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.forecast_table.setItem(r, 2, it2)
            
            it3 = QTableWidgetItem(f"CHF {chf(forecast)}")
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.forecast_table.setItem(r, 3, it3)
            
            it4 = QTableWidgetItem(f"CHF {chf(diff)}")
            it4.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Farbcodierung
            if typ == "Ausgaben":
                if diff > 0:
                    it4.setForeground(QColor(255, 100, 100))  # Rot = Mehr als Budget
                elif diff < 0:
                    it4.setForeground(QColor(100, 200, 100))  # Grün = Weniger als Budget
            else:
                if diff > 0:
                    it4.setForeground(QColor(100, 200, 100))  # Grün = Mehr als Budget
                elif diff < 0:
                    it4.setForeground(QColor(255, 100, 100))  # Rot = Weniger als Budget
            
            self.forecast_table.setItem(r, 4, it4)
        
        self.forecast_table.resizeColumnsToContents()
        
        # Trend-Chart aktualisieren
        self._update_trend_chart(year)
    
    def _update_trend_chart(self, year: int):
        """Aktualisiert das Trend-Diagramm"""
        if not hasattr(self, 'trend_chart'):
            return
        
        # Monatliche Ausgaben
        ausgaben = self.track.sum_by_month(year, typ="Ausgaben")
        
        series = QLineSeries()
        series.setName(f"Ausgaben {year}")
        
        for m in range(1, 13):
            series.append(m, float(ausgaben.get(m, 0)))
        
        chart = QChart()
        chart.setTitle(f"Monatliche Ausgaben {year}")
        chart.addSeries(series)
        chart.legend().setVisible(True)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Achsen
        ax_x = QBarCategoryAxis()
        ax_x.append(MONTH_NAMES_SHORT)
        chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)
        
        ax_y = QValueAxis()
        vals = list(ausgaben.values())
        ax_y.setRange(0, max(vals) * 1.1 if vals else 1000)
        chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)
        
        self.trend_chart.setRenderHint(QPainter.Antialiasing)
        self.trend_chart.setChart(chart)
    
    def _update_year_comparison(self):
        """Aktualisiert den Jahresvergleich"""
        if not hasattr(self, 'comparison_table'):
            return
        
        try:
            year1 = int(self.compare_year1.currentText())
            year2 = int(self.compare_year2.currentText())
        except:
            return
        
        self.comparison_table.setRowCount(0)
        
        # Header aktualisieren
        self.comparison_table.setHorizontalHeaderLabels([
            "Typ", str(year1), str(year2), "Differenz", "Änderung %"
        ])
        
        for typ in ["Einkommen", "Ausgaben", "Ersparnisse"]:
            val1 = self.track.sum_by_typ(year=year1, month=None).get(typ, 0)
            val2 = self.track.sum_by_typ(year=year2, month=None).get(typ, 0)
            
            diff = val1 - val2
            pct = ((val1 - val2) / val2 * 100) if val2 != 0 else 0
            
            r = self.comparison_table.rowCount()
            self.comparison_table.insertRow(r)
            
            self.comparison_table.setItem(r, 0, QTableWidgetItem(typ))
            
            it1 = QTableWidgetItem(f"CHF {chf(val1)}")
            it1.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.comparison_table.setItem(r, 1, it1)
            
            it2 = QTableWidgetItem(f"CHF {chf(val2)}")
            it2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.comparison_table.setItem(r, 2, it2)
            
            it3 = QTableWidgetItem(f"CHF {chf(diff)}")
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if diff > 0:
                it3.setForeground(QColor(100, 200, 100))
            elif diff < 0:
                it3.setForeground(QColor(255, 100, 100))
            self.comparison_table.setItem(r, 3, it3)
            
            it4 = QTableWidgetItem(f"{pct:+.1f}%")
            it4.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if pct > 0:
                it4.setForeground(QColor(100, 200, 100))
            elif pct < 0:
                it4.setForeground(QColor(255, 100, 100))
            self.comparison_table.setItem(r, 4, it4)
        
        self.comparison_table.resizeColumnsToContents()
        
        # Vergleichs-Chart
        self._update_comparison_chart(year1, year2)
    
    def _update_comparison_chart(self, year1: int, year2: int):
        """Aktualisiert das Vergleichs-Diagramm"""
        if not hasattr(self, 'comparison_chart'):
            return
        
        set1 = QBarSet(str(year1))
        set2 = QBarSet(str(year2))
        
        categories = []
        for typ in ["Einkommen", "Ausgaben", "Ersparnisse"]:
            val1 = self.track.sum_by_typ(year=year1, month=None).get(typ, 0)
            val2 = self.track.sum_by_typ(year=year2, month=None).get(typ, 0)
            set1.append(float(val1))
            set2.append(float(val2))
            categories.append(typ)
        
        series = QBarSeries()
        series.append(set1)
        series.append(set2)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(f"Vergleich {year1} vs {year2}")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        all_vals = [set1.at(i) for i in range(set1.count())] + [set2.at(i) for i in range(set2.count())]
        axis_y.setRange(0, max(all_vals) * 1.1 if all_vals else 1000)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        self.comparison_chart.setRenderHint(QPainter.Antialiasing)
        self.comparison_chart.setChart(chart)
    
    def _set_dashboard_charts(self, data: dict[str, float], title: str, view: QChartView):
        """Setzt Charts im Dashboard basierend auf aktuellem Typ"""
        chart_type = getattr(self, 'current_chart_type', 'pie')
        
        if chart_type == "pie":
            self._set_pie(view, data)
        elif chart_type == "bar":
            self._set_vertical_bar(view, data, title)
        elif chart_type == "hbar":
            self._set_horizontal_bar(view, data, title)
    
    def _set_vertical_bar(self, view: QChartView, data: dict[str, float], title: str):
        """Erstellt ein vertikales Balkendiagramm"""
        series = QBarSeries()
        
        for key, val in data.items():
            bar_set = QBarSet(key)
            bar_set.append(abs(float(val)))
            series.append(bar_set)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        axis_y = QValueAxis()
        vals = [abs(float(v)) for v in data.values()]
        axis_y.setRange(0, max(vals) * 1.1 if vals else 1000)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        view.setRenderHint(QPainter.Antialiasing)
        view.setChart(chart)
    
    def _set_horizontal_bar(self, view: QChartView, data: dict[str, float], title: str):
        """Erstellt ein horizontales Balkendiagramm"""
        series = QHorizontalBarSeries()
        
        for key, val in data.items():
            bar_set = QBarSet(key)
            bar_set.append(abs(float(val)))
            series.append(bar_set)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        axis_x = QValueAxis()
        vals = [abs(float(v)) for v in data.values()]
        axis_x.setRange(0, max(vals) * 1.1 if vals else 1000)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        view.setRenderHint(QPainter.Antialiasing)
        view.setChart(chart)