"""KPI-Panel der Finanzübersicht: KPI-Cards, Progress-Bars und Diagramm-Tab.

Extrahiert aus overview_tab.py (v1.0.5 – Patch C: Aufspaltung).

Verantwortlich für:
- 4 KPI-Cards (Einkommen, Ausgaben, Bilanz, Ersparnisse)
- 3 Progress-Bars (Budget vs. Ist)
- Diagramm-Tab mit Drill-Down (Nested Donut + Bar Chart)
- Kategorien-Pie-Chart
- Typ-Verteilungs-Chart
- Sinnvolle Zusatzgraphen: Monatsverlauf, Monatsbilanz, Top-Buchungen

Schnittstelle zu OverviewTab:
    panel = OverviewKpiPanel(budget_overview_model, parent=self)
    panel.build_tab_widget()   → gibt QWidget zurück (Diagram-Tab)
    panel.refresh(rows, budget_sums, year, month_idx)
    panel.kpi_clicked.connect(...)  → emittiert Typ-String bei Card-Klick
    panel.chart_category_clicked.connect(...)  → emittiert Kategorie-Name
    panel.chart_type_clicked.connect(...)  → emittiert Typ-Name
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from datetime import date

from model.date_ranges import month_bounds

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QStackedWidget,
    QSizePolicy,
)

from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from model.budget_overview_model import BudgetOverviewModel
from utils.i18n import tr, display_typ, db_typ_from_display, trf
from utils.money import format_money as format_chf
from views.ui_colors import ui_colors
from views.tabs.overview_widgets import CompactKPICard, CompactProgressBar, CompactChart

from model.typ_constants import (
    normalize_typ as _norm,
    TYP_INCOME,
    TYP_EXPENSES,
    TYP_SAVINGS,
)


class OverviewKpiPanel(QWidget):
    """KPI-Cards + Progress-Bars + Chart-Tabs als einzelnes Widget."""

    # Signale für den Orchestrator (OverviewTab)
    kpi_clicked = Signal(str)  # Typ-String (tr("lbl.all") / TYP_INCOME / …)
    chart_category_clicked = Signal(str)  # Kategorien-Slice-Klick
    chart_type_clicked = Signal(str)  # Typ-Slice-Klick

    def __init__(self, budget_overview: BudgetOverviewModel, parent=None):
        super().__init__(parent)
        self.budget_overview = budget_overview
        self._setup_ui()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ── KPI Cards ──
        self.kpi_widget = QWidget()
        kpi_layout = QHBoxLayout(self.kpi_widget)
        kpi_layout.setSpacing(8)
        kpi_layout.setContentsMargins(0, 0, 0, 0)

        c = ui_colors(self)
        self.card_income = CompactKPICard(
            tr("kpi.income"), format_chf(0), "💰", c.type_color(TYP_INCOME)
        )
        self.card_expenses = CompactKPICard(
            tr("kpi.expenses"), format_chf(0), "💸", c.type_color(TYP_EXPENSES)
        )
        self.card_balance = CompactKPICard(
            tr("lbl.bilanz"), format_chf(0), "📊", c.type_color(TYP_SAVINGS)
        )
        self.card_savings = CompactKPICard(
            tr("kpi.savings"), format_chf(0), "🏦", c.type_color(TYP_SAVINGS)
        )

        self.card_income.clicked.connect(lambda: self.kpi_clicked.emit(TYP_INCOME))
        self.card_expenses.clicked.connect(lambda: self.kpi_clicked.emit(TYP_EXPENSES))
        self.card_balance.clicked.connect(lambda: self.kpi_clicked.emit(""))
        self.card_savings.clicked.connect(lambda: self.kpi_clicked.emit(TYP_SAVINGS))

        for card in (
            self.card_income,
            self.card_expenses,
            self.card_balance,
            self.card_savings,
        ):
            kpi_layout.addWidget(card)
        layout.addWidget(self.kpi_widget)

        # ── Progress Bars ──
        self.pb_income = CompactProgressBar(tr("kpi.income"), 1000, typ_key=TYP_INCOME)
        self.pb_expenses = CompactProgressBar(
            tr("kpi.expenses"), 1000, typ_key=TYP_EXPENSES
        )
        self.pb_savings = CompactProgressBar(
            tr("kpi.savings"), 1000, typ_key=TYP_SAVINGS
        )
        layout.addWidget(self.pb_income)
        layout.addWidget(self.pb_expenses)
        layout.addWidget(self.pb_savings)

        # ── Chart Tabs ──
        self.chart_tabs = QTabWidget()
        self.chart_tabs.addTab(self._build_donut_tab(), tr("tab.chart_overview"))
        self.chart_tabs.addTab(self._build_cat_tab(), tr("overview.subtab.categories"))
        self.chart_tabs.addTab(
            self._build_typ_tab(), tr("overview.subtab.distribution")
        )
        self.chart_tabs.addTab(
            self._build_monthly_trend_tab(), tr("overview.subtab.monthly_trend")
        )
        self.chart_tabs.addTab(
            self._build_balance_trend_tab(), tr("overview.subtab.balance_trend")
        )
        self.chart_tabs.addTab(
            self._build_top_bookings_tab(), tr("overview.subtab.top_bookings")
        )
        layout.addWidget(self.chart_tabs)
        layout.addStretch()

    def _build_donut_tab(self) -> QWidget:
        """Nested-Donut mit Drill-Down Stacked-Widget."""
        self.chart_overview_stack = QStackedWidget()

        # Page 0: Nested Donut
        p0 = QWidget()
        p0l = QVBoxLayout(p0)
        p0l.setContentsMargins(0, 0, 0, 0)
        self.chart_overview_donut = CompactChart()
        self.chart_overview_donut.setMinimumHeight(280)
        self.chart_overview_donut.setMaximumHeight(420)
        self.chart_overview_donut.slice_clicked.connect(self._on_donut_clicked)
        p0l.addWidget(self.chart_overview_donut)
        self.chart_overview_stack.addWidget(p0)

        # Page 1: Drill-Down
        p1 = QWidget()
        p1l = QVBoxLayout(p1)
        p1l.setContentsMargins(0, 0, 0, 0)
        p1l.setSpacing(4)

        dd_hdr = QHBoxLayout()
        self.btn_drilldown_back = QPushButton(tr("btn.back"))
        self.btn_drilldown_back.setFixedWidth(180)
        self.btn_drilldown_back.clicked.connect(
            lambda: self.chart_overview_stack.setCurrentIndex(0)
        )
        dd_hdr.addWidget(self.btn_drilldown_back)
        self.lbl_drilldown_title = QLabel()
        self.lbl_drilldown_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        dd_hdr.addWidget(self.lbl_drilldown_title)
        dd_hdr.addStretch()
        p1l.addLayout(dd_hdr)

        self.chart_drilldown_budget = CompactChart()
        self.chart_drilldown_budget.setMinimumHeight(200)
        self.chart_drilldown_budget.setMaximumHeight(300)
        p1l.addWidget(self.chart_drilldown_budget)

        self.chart_drilldown_open = CompactChart()
        self.chart_drilldown_open.setMinimumHeight(180)
        self.chart_drilldown_open.setMaximumHeight(260)
        p1l.addWidget(self.chart_drilldown_open)
        p1l.addStretch()
        self.chart_overview_stack.addWidget(p1)

        return self.chart_overview_stack

    def _build_cat_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.chart_categories = CompactChart()
        self.chart_categories.slice_clicked.connect(self.chart_category_clicked)
        l.addWidget(self.chart_categories)
        return w

    def _build_typ_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.chart_types = CompactChart()
        self.chart_types.slice_clicked.connect(
            lambda s: self.chart_type_clicked.emit(db_typ_from_display(s) if s else "")
        )
        l.addWidget(self.chart_types)
        return w

    def _build_monthly_trend_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.chart_monthly_expenses = CompactChart()
        self.chart_monthly_expenses.setMinimumHeight(260)
        self.chart_monthly_expenses.setMaximumHeight(420)
        self.chart_monthly_expenses.setToolTip(tr("overview.tip.monthly_trend"))
        l.addWidget(self.chart_monthly_expenses)
        return w

    def _build_balance_trend_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.chart_monthly_balance = CompactChart()
        self.chart_monthly_balance.setMinimumHeight(260)
        self.chart_monthly_balance.setMaximumHeight(420)
        self.chart_monthly_balance.setToolTip(tr("overview.tip.balance_trend"))
        l.addWidget(self.chart_monthly_balance)
        return w

    def _build_top_bookings_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.chart_top_bookings = CompactChart()
        self.chart_top_bookings.setMinimumHeight(260)
        self.chart_top_bookings.setMaximumHeight(420)
        self.chart_top_bookings.setToolTip(tr("overview.tip.top_bookings"))
        l.addWidget(self.chart_top_bookings)
        return w

    # ── Daten laden ─────────────────────────────────────────────────────────
    # ── Daten laden ─────────────────────────────────────────────────────────

    def refresh_kpis(self, rows: list, budget_sums: dict[str, float]) -> None:
        """KPI-Cards und Progress-Bars aktualisieren."""
        total_income = sum(r.amount for r in rows if _norm(r.typ) == TYP_INCOME)
        total_expenses = sum(
            abs(r.amount) for r in rows if _norm(r.typ) == TYP_EXPENSES
        )
        total_savings = sum(r.amount for r in rows if _norm(r.typ) == TYP_SAVINGS)
        balance = total_income - total_expenses

        self.card_income.update_value(format_chf(total_income))
        self.card_expenses.update_value(format_chf(total_expenses))
        self.card_savings.update_value(format_chf(total_savings))
        c = ui_colors(self)
        self.card_balance.update_value(format_chf(balance), c.amount_color(balance))

        # budget_sums nutzt DB-Schluessel (TYP_*), nicht uebersetzte Namen
        b_income = float(budget_sums.get(TYP_INCOME, 0.0))
        b_expenses = float(budget_sums.get(TYP_EXPENSES, 0.0))
        b_savings = float(budget_sums.get(TYP_SAVINGS, 0.0))
        self.pb_income.set_values(total_income, b_income)
        self.pb_expenses.set_values(total_expenses, b_expenses)
        self.pb_savings.set_values(total_savings, b_savings)

    def _month_pairs_for_chart(
        self, year: int, month_idx: int, date_from: date | None, date_to: date | None
    ) -> list[tuple[int, int]]:
        """Monatsliste für Verlaufsdiagramme.

        Jahr/Monat-Auswahl: immer voller Jahreskontext, bei Monatsauswahl
        trotzdem 12 Monate, weil der Verlauf sonst keinen Nutzen hätte.
        Benutzerdefinierte/rollierende Bereiche: Monate im gewählten Bereich.
        """
        if date_from is None or date_to is None:
            return [(year, m) for m in range(1, 13)]

        # Reiner Jahr/Monat-Fall: voller Jahresverlauf.
        if date_from == date(year, 1, 1) and date_to == date(year, 12, 31):
            return [(year, m) for m in range(1, 13)]
        if (
            month_idx > 0
            and date_from.year == year
            and date_to.year == year
            and date_from.month == month_idx
            and date_to.month == month_idx
        ):
            return [(year, m) for m in range(1, 13)]

        pairs: list[tuple[int, int]] = []
        y, m = date_from.year, date_from.month
        end_y, end_m = date_to.year, date_to.month
        while (y, m) <= (end_y, end_m):
            pairs.append((y, m))
            if m == 12:
                y += 1
                m = 1
            else:
                m += 1

        # Lesbarkeit: maximal 24 Monate im Chart, sonst wird die Achse unbrauchbar.
        return pairs[-24:] if len(pairs) > 24 else pairs

    def _month_label_for_chart(
        self, year: int, month: int, all_pairs: list[tuple[int, int]]
    ) -> str:
        label = tr(f"month_short.{month}")
        years = {y for y, _m in all_pairs}
        return f"{label} {year}" if len(years) > 1 else label

    def _monthly_amount(self, table: str, year: int, month: int, typ: str) -> float:
        if table == "budget":
            return float(self.budget_overview.budget_sum(year, month, typ))
        start, end = month_bounds(year, month)
        row = self.budget_overview.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM tracking WHERE date >= ? AND date < ? AND typ = ?",
            (start, end, typ),
        ).fetchone()
        val = float(row[0] or 0.0) if row else 0.0
        return abs(val) if typ == TYP_EXPENSES else val

    def refresh_charts(
        self,
        rows: list,
        year: int,
        month_idx: int,
        date_from: date | None = None,
        date_to: date | None = None,
        budget_sums: dict | None = None,
    ) -> None:
        """Charts neu zeichnen."""
        self.chart_overview_stack.setCurrentIndex(0)

        _cc = ui_colors(self)

        income_actual = sum(r.amount for r in rows if _norm(r.typ) == TYP_INCOME)
        expense_actual = sum(
            abs(r.amount) for r in rows if _norm(r.typ) == TYP_EXPENSES
        )
        savings_actual = sum(r.amount for r in rows if _norm(r.typ) == TYP_SAVINGS)

        # Budget-Daten — bereichsbezogen.
        # Wird budget_sums (über die Monate des gewählten Zeitraums summiert)
        # übergeben, nutzen wir das. So passt das Donut-Budget zum tatsächlich
        # gewählten Zeitraum (auch bei rollierenden Bereichen wie 7/30/90 Tagen)
        # und ist konsistent mit der KPI-Leiste. Fallback: alte month_idx-Logik.
        income_budget = expense_budget = savings_budget = 0.0
        if budget_sums is not None:
            income_budget = float(budget_sums.get(TYP_INCOME, 0.0))
            expense_budget = float(budget_sums.get(TYP_EXPENSES, 0.0))
            savings_budget = float(budget_sums.get(TYP_SAVINGS, 0.0))
        else:
            try:
                if month_idx == 0:
                    income_budget = sum(
                        self.budget_overview.budget_sum(year, m, TYP_INCOME)
                        for m in range(1, 13)
                    )
                    expense_budget = sum(
                        self.budget_overview.budget_sum(year, m, TYP_EXPENSES)
                        for m in range(1, 13)
                    )
                    savings_budget = sum(
                        self.budget_overview.budget_sum(year, m, TYP_SAVINGS)
                        for m in range(1, 13)
                    )
                else:
                    income_budget = self.budget_overview.budget_sum(
                        year, month_idx, TYP_INCOME
                    )
                    expense_budget = self.budget_overview.budget_sum(
                        year, month_idx, TYP_EXPENSES
                    )
                    savings_budget = self.budget_overview.budget_sum(
                        year, month_idx, TYP_SAVINGS
                    )
            except Exception as e:
                logger.debug("budget_sum: %s", e)

        income_open = max(0, income_budget - income_actual)
        expense_open = max(0, expense_budget - expense_actual)
        savings_open = max(0, savings_budget - savings_actual)

        ring_data = []

        # Ring 1 (aussen): Einkommen
        eink_slices = []
        if income_actual > 0:
            eink_slices.append(
                {
                    "label": f"{tr('lbl.gebucht')}: {format_chf(income_actual)}",
                    "value": income_actual,
                    "color": _cc.budget_chart_colors(TYP_INCOME)["gebucht"],
                    "raw_label": TYP_INCOME,
                }
            )
        if income_open > 0:
            eink_slices.append(
                {
                    "label": f"{tr('lbl.offen')}: {format_chf(income_open)}",
                    "value": income_open,
                    "color": _cc.budget_chart_colors(TYP_INCOME)["offen"],
                    "raw_label": TYP_INCOME,
                }
            )
        if eink_slices:
            ring_data.append(
                {
                    "label": tr("kpi.income"),
                    "slices": eink_slices,
                    "pie_size": 0.92,
                    "hole_size": 0.68,
                }
            )

        # Ring 2 (mitte): Ausgaben
        ausg_slices = []
        if expense_actual > 0:
            eink_ref = max(income_actual, income_budget, 1)
            pct_spent = (expense_actual / eink_ref) * 100
            ausg_slices.append(
                {
                    "label": f"{tr('lbl.gebucht')}: {format_chf(expense_actual)} ({pct_spent:.0f}%)",
                    "value": expense_actual,
                    "color": _cc.budget_chart_colors(TYP_EXPENSES)["gebucht"],
                    "raw_label": TYP_EXPENSES,
                }
            )
        if expense_open > 0:
            ausg_slices.append(
                {
                    "label": f"{tr('lbl.offen')}: {format_chf(expense_open)}",
                    "value": expense_open,
                    "color": _cc.budget_chart_colors(TYP_EXPENSES)["offen"],
                    "raw_label": TYP_EXPENSES,
                }
            )
        if ausg_slices:
            ring_data.append(
                {
                    "label": tr("kpi.expenses"),
                    "slices": ausg_slices,
                    "pie_size": 0.65,
                    "hole_size": 0.42,
                }
            )

        # Ring 3 (innen): Ersparnisse
        spar_slices = []
        if savings_actual > 0:
            spar_slices.append(
                {
                    "label": f"{tr('lbl.gebucht')}: {format_chf(savings_actual)}",
                    "value": savings_actual,
                    "color": _cc.budget_chart_colors(TYP_SAVINGS)["gebucht"],
                    "raw_label": TYP_SAVINGS,
                }
            )
        if savings_open > 0:
            spar_slices.append(
                {
                    "label": f"{tr('lbl.offen')}: {format_chf(savings_open)}",
                    "value": savings_open,
                    "color": _cc.budget_chart_colors(TYP_SAVINGS)["offen"],
                    "raw_label": TYP_SAVINGS,
                }
            )
        if spar_slices:
            ring_data.append(
                {
                    "label": display_typ(TYP_SAVINGS),
                    "slices": spar_slices,
                    "pie_size": 0.39,
                    "hole_size": 0.18,
                }
            )

        self.chart_overview_donut.create_nested_donut(ring_data)

        # Kategorien-Pie (Ausgaben) – farblich am Kontotyp orientiert.
        # Einnahmen=grün, Ausgaben=rot, Ersparnisse=blau. Da dieser Tab
        # Ausgaben zeigt, bleiben alle Ausgaben-Kategorien konsistent rot.
        cat_data: dict[str, float] = {}
        cat_colors: dict[str, str] = {}
        for r in rows:
            if _norm(r.typ) == TYP_EXPENSES:
                cat_data[r.category] = cat_data.get(r.category, 0) + abs(r.amount)
                cat_colors[r.category] = _cc.type_color(TYP_EXPENSES)
        self.chart_categories.create_pie_chart(
            cat_data,
            tr("tab_ui.ausgaben_nach_kategorie"),
            color_map=cat_colors,
        )

        # Typ-Verteilung – Display-Keys damit chart_types.slice_clicked
        # einen übersetzten String emittiert den db_typ_from_display() versteht
        typ_data = {
            display_typ(TYP_INCOME): income_actual,
            display_typ(TYP_EXPENSES): expense_actual,
            display_typ(TYP_SAVINGS): savings_actual,
        }
        type_colors = {
            display_typ(TYP_INCOME): _cc.budget_chart_colors(TYP_INCOME)["gebucht"],
            display_typ(TYP_EXPENSES): _cc.budget_chart_colors(TYP_EXPENSES)["gebucht"],
            display_typ(TYP_SAVINGS): _cc.budget_chart_colors(TYP_SAVINGS)["gebucht"],
        }
        self.chart_types.create_pie_chart(
            {k: v for k, v in typ_data.items() if v > 0},
            tr("tab_ui.verteilung_nach_typ"),
            color_map=type_colors,
        )

        # Sinnvolle Zusatzgraphen: Verlauf statt weitere Kreisdiagramme.
        self._refresh_monthly_trend_charts(rows, year, month_idx, date_from, date_to)

        # Drill-Down Daten für spätere Nutzung cachen
        self._last_year = year
        self._last_month_idx = month_idx

    def _refresh_monthly_trend_charts(
        self,
        rows: list,
        year: int,
        month_idx: int,
        date_from: date | None,
        date_to: date | None,
    ) -> None:
        pairs = self._month_pairs_for_chart(year, month_idx, date_from, date_to)
        labels = [self._month_label_for_chart(y, m, pairs) for y, m in pairs]
        c = ui_colors(self)

        expense_actual = [
            self._monthly_amount("tracking", y, m, TYP_EXPENSES) for y, m in pairs
        ]
        expense_budget = [
            self._monthly_amount("budget", y, m, TYP_EXPENSES) for y, m in pairs
        ]
        self.chart_monthly_expenses.create_line_chart(
            labels,
            [
                {
                    "label": tr("lbl.gebucht"),
                    "values": expense_actual,
                    "color": c.budget_chart_colors(TYP_EXPENSES)["gebucht"],
                },
                {
                    "label": tr("header.budget"),
                    "values": expense_budget,
                    "color": c.budget_chart_colors(TYP_EXPENSES)["budget"],
                },
            ],
            tr("chart.monthly_expenses_budget_actual"),
        )

        balance_actual = []
        balance_budget = []
        for y, m in pairs:
            inc_actual = self._monthly_amount("tracking", y, m, TYP_INCOME)
            exp_actual = self._monthly_amount("tracking", y, m, TYP_EXPENSES)
            inc_budget = self._monthly_amount("budget", y, m, TYP_INCOME)
            exp_budget = self._monthly_amount("budget", y, m, TYP_EXPENSES)
            balance_actual.append(inc_actual - exp_actual)
            balance_budget.append(inc_budget - exp_budget)

        self.chart_monthly_balance.create_line_chart(
            labels,
            [
                {
                    "label": tr("lbl.bilanz"),
                    "values": balance_actual,
                    "color": c.amount_color(sum(balance_actual)),
                },
                {
                    "label": tr("chart.planned_balance"),
                    "values": balance_budget,
                    "color": c.text_dim,
                },
            ],
            tr("chart.monthly_balance"),
        )

        # Top-Buchungen: pro Kategorie aggregieren (z.B. mehrere Lohn-Buchungen
        # im Zeitraum werden zu EINEM Balken summiert), dann die größten 5 zeigen.
        from model.overview_aggregation import aggregate_top_bookings

        top_items = aggregate_top_bookings(rows, top_n=5)
        top_bars = []
        for (typ_db, cat), total in top_items:
            label = cat if len(cat) <= 22 else cat[:21] + "…"
            top_bars.append(
                {
                    "label": label,
                    "value": total,
                    "color": c.type_color(typ_db),
                }
            )

        self.chart_top_bookings.create_colored_bar_chart(
            bars=top_bars,
            title=tr("chart.top_bookings_by_amount"),
        )

    # ── Drill-Down ──────────────────────────────────────────────────────────

    def _on_donut_clicked(self, typ_name: str) -> None:
        """Klick im Donut → Drill-Down für diesen Typ."""
        if not typ_name:
            return

        _c = ui_colors(self)

        # typ_name kann DB-Key oder Display-Text sein.
        from utils.i18n import db_typ_from_display

        typ_db = _norm(typ_name)
        if typ_db not in (TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS):
            typ_db = db_typ_from_display(typ_name)

        colors = _c.budget_chart_colors(typ_db)

        year = getattr(self, "_last_year", date.today().year)
        month_idx = getattr(self, "_last_month_idx", 0)
        months = list(range(1, 13)) if month_idx == 0 else [month_idx]

        try:
            budget_cats = self.budget_overview.budget_by_category_range(
                year, months, typ_db
            )
            actual_cats = self.budget_overview.actual_by_category_range(
                year, months, typ_db
            )
        except Exception:
            budget_cats, actual_cats = {}, {}

        all_cats = set(budget_cats.keys()) | set(actual_cats.keys())
        if not all_cats:
            return

        cat_data = sorted(
            [
                (
                    cat,
                    budget_cats.get(cat, 0.0),
                    actual_cats.get(cat, 0.0),
                    max(0.0, budget_cats.get(cat, 0.0) - actual_cats.get(cat, 0.0)),
                )
                for cat in all_cats
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:6]

        from utils.i18n import trf
        from views.tabs.overview_widgets import CompactChart  # already imported

        labels = [x[0] for x in cat_data]
        budget_vals = [x[1] for x in cat_data]
        actual_vals = [x[2] for x in cat_data]
        open_vals = [x[3] for x in cat_data]

        from utils.i18n import tr as _tr

        month_label = (
            _tr("lbl.entire_year")
            if month_idx <= 0
            else _tr(f"month_short.{month_idx}")
        )
        self.lbl_drilldown_title.setText(
            trf(
                "auto.views_tabs_overview_kpi_panel.346_value_0_value_1_value_2_294a97b0",
                value_0=(typ_name),
                value_1=(month_label),
                value_2=(year),
            )
        )

        self.chart_drilldown_budget.create_grouped_bar_chart(
            categories=labels,
            series_data=[
                {
                    "label": tr("header.budget"),
                    "values": budget_vals,
                    "color": colors["budget"],
                },
                {
                    "label": tr("lbl.gebucht"),
                    "values": actual_vals,
                    "color": colors["gebucht"],
                },
            ],
            title=tr("chart.top6_budget_vs_actual"),
        )

        open_cats_data = [
            (labels[i], open_vals[i])
            for i in range(len(cat_data))
            if open_vals[i] > 0.01
        ]
        if open_cats_data:
            self.chart_drilldown_open.create_pie_chart(
                {c: v for c, v in open_cats_data},
                title=tr("chart.open_budgeted_amounts"),
            )
        else:
            self.chart_drilldown_open.create_pie_chart(
                {}, title=_tr("tab_ui.keine_offenen_betraege")
            )

        self.chart_overview_stack.setCurrentIndex(1)
