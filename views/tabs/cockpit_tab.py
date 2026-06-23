from __future__ import annotations

import logging
import sqlite3
from datetime import date
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QGridLayout,
    QScrollArea,
    QMenu,
    QSizePolicy,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QAbstractScrollArea,
)

from model.favorites_model import FavoritesModel
from model.savings_goals_model import SavingsGoalsModel, STATUS_SAVING, STATUS_RELEASED
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from model.date_ranges import month_bounds
from utils.i18n import display_typ, tr
from settings import Settings
from utils.money import format_money
from utils.icons import get_icon

logger = logging.getLogger(__name__)


class _Card(QFrame):
    def __init__(self, title: str, value: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("cockpitCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-weight: 600;")
        self.lbl_value = QLabel(value, self)
        self.lbl_value.setWordWrap(True)
        self.lbl_value.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.lbl_hint = QLabel(hint, self)
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color: #666;")
        # WICHTIG: Das Hinweis-Label immer ins Layout aufnehmen.
        # Vorher wurde es bei leerem Start-Hinweis nicht eingehängt und blieb
        # parentlos. Sobald set_values(..., hint) später setVisible(True) aufrief,
        # machte Qt daraus ein eigenes Top-Level-Fenster mit dem Programmtitel.
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_value)
        lay.addWidget(self.lbl_hint)
        self.lbl_hint.setVisible(bool(hint))

    def set_values(self, value: str, hint: str = ""):
        self.lbl_value.setText(value)
        self.lbl_hint.setText(hint)
        self.lbl_hint.setVisible(bool(hint))


class CockpitTab(QWidget):
    """Start-Cockpit: kompakte Einstiegseite ohne die Fach-Reiter zu ersetzen.

    Designziel: Nutzer sieht die wichtigsten Aufgaben und kann mit einem Klick in den
    richtigen Bereich springen. Details bleiben in Budget, Buchungen, Übersicht und
    Sparziele, damit das Cockpit nicht überladen wird.
    """

    quick_add_requested = Signal()
    fixcost_requested = Signal()
    favorites_requested = Signal()
    savings_requested = Signal()
    goto_budget_requested = Signal()
    goto_tracking_requested = Signal()
    goto_overview_requested = Signal()
    goto_savings_requested = Signal()
    budget_warnings_requested = Signal()

    PANEL_DEFAULTS = {
        "kpis": True,
        "quick_actions": True,
        "favorites": True,
        "savings": True,
        "warnings": True,
        "budget_warnings": True,
        "missing": True,
        "recent": True,
    }

    PANEL_TITLE_KEYS = {
        "kpis": "cockpit.panel.kpis",
        "quick_actions": "cockpit.panel.quick_actions",
        "favorites": "cockpit.panel.favorites",
        "savings": "cockpit.panel.savings",
        "warnings": "cockpit.panel.warnings",
        "budget_warnings": "cockpit.panel.budget_warnings",
        "missing": "cockpit.panel.missing",
        "recent": "cockpit.panel.recent",
    }
    PANEL_ORDER_DEFAULTS = list(PANEL_DEFAULTS.keys())

    def __init__(self, conn: sqlite3.Connection, settings: Settings | None = None):
        super().__init__()
        self.conn = conn
        self.settings = settings or Settings()
        self._ensure_budget_warnings_panel_visible()
        self._warnings_model_ext = None  # lazy: BudgetWarningsModelExtended
        self._panel_widgets: dict[str, QWidget] = {}
        self._setup_ui()
        self.refresh()

    def _ensure_budget_warnings_panel_visible(self) -> None:
        """Budgetwarnungen im Cockpit standardmäßig sichtbar halten.

        Frühere Builds konnten die Warnbereiche über gespeicherte Einstellungen
        ausblenden. Nach dem Merge sollen die Budget-Ampel und die eigentlichen
        Budgetwarnungen sichtbar sein, bis der Nutzer sie bewusst ausblendet.
        """
        try:
            marker = "cockpit_warnings_visible_migrated_v2014"
            if self.settings.get(marker, False):
                return
            cfg = self.settings.get("cockpit_visible_panels", {}) or {}
            cfg = {
                **self.PANEL_DEFAULTS,
                **cfg,
                "warnings": True,
                "budget_warnings": True,
            }
            self.settings.set("cockpit_visible_panels", cfg)
            self.settings.set(marker, True)
        except Exception:
            pass

    # ── UI ───────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(14, 14, 14, 14)
        self.body_layout.setSpacing(12)
        scroll.setWidget(body)
        root.addWidget(scroll)

        header = QHBoxLayout()
        title = QLabel(tr("cockpit.title"))
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        subtitle = QLabel(tr("cockpit.subtitle"))
        subtitle.setStyleSheet("color: #666;")
        title_box = QVBoxLayout()
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.btn_customize = QPushButton(tr("cockpit.customize"))
        self.btn_customize.setToolTip(tr("cockpit.customize_tip"))
        self.btn_customize.clicked.connect(self._show_customize_menu)
        header.addWidget(self.btn_customize)
        self.btn_refresh = QPushButton(tr("cockpit.refresh"))
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        self.body_layout.addLayout(header)

        # KPIs
        self.kpi_panel = QWidget()
        kpi_lay = QGridLayout(self.kpi_panel)
        kpi_lay.setContentsMargins(0, 0, 0, 0)
        self.card_income = _Card(display_typ(TYP_INCOME), "–")
        self.card_expenses = _Card(display_typ(TYP_EXPENSES), "–")
        self.card_savings = _Card(display_typ(TYP_SAVINGS), "–")
        self.card_balance = _Card(tr("cockpit.month_feeling"), "–")
        # 2x2 statt 4 nebeneinander: deutlich robuster bei Windows 125/150 %,
        # kleinen Notebook-Displays und portabler Nutzung an fremden Monitoren.
        for i, card in enumerate(
            [self.card_income, self.card_expenses, self.card_savings, self.card_balance]
        ):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            card.setMinimumWidth(0)
            row, col = divmod(i, 2)
            kpi_lay.addWidget(card, row, col)
        kpi_lay.setColumnStretch(0, 1)
        kpi_lay.setColumnStretch(1, 1)
        self._add_panel("kpis", self.kpi_panel)

        # Quick actions
        self.actions_panel = self._section(tr("cockpit.panel.quick_actions"))
        act_lay = QGridLayout(self.actions_panel)
        act_lay.setContentsMargins(10, 28, 10, 10)
        act_lay.setHorizontalSpacing(8)
        act_lay.setVerticalSpacing(8)
        for i, (label, slot, tip) in enumerate(
            [
                (
                    tr("cockpit.action_quick_add"),
                    self.quick_add_requested.emit,
                    tr("cockpit.action_quick_add_tip"),
                ),
                (
                    tr("cockpit.action_fixcosts"),
                    self.fixcost_requested.emit,
                    tr("cockpit.action_fixcosts_tip"),
                ),
                (
                    tr("cockpit.action_check_budget"),
                    self.goto_budget_requested.emit,
                    tr("cockpit.action_check_budget_tip"),
                ),
                (
                    tr("cockpit.action_budget_warnings"),
                    self.budget_warnings_requested.emit,
                    tr("cockpit.action_budget_warnings_tip"),
                ),
                (
                    tr("cockpit.action_savings"),
                    self.savings_requested.emit,
                    tr("cockpit.action_savings_tip"),
                ),
                (
                    tr("cockpit.action_overview"),
                    self.goto_overview_requested.emit,
                    tr("cockpit.action_overview_tip"),
                ),
            ]
        ):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            b.clicked.connect(slot)
            row, col = divmod(i, 3)
            act_lay.addWidget(b, row, col)
        for col in range(3):
            act_lay.setColumnStretch(col, 1)
        self._add_panel("quick_actions", self.actions_panel)

        # Main grid-ish rows
        self.favorites_panel = self._table_section(
            tr("cockpit.panel.favorites"),
            [
                tr("col.typ"),
                tr("col.kategorie"),
                tr("col.budget"),
                tr("col.gebucht"),
                tr("col.rest"),
            ],
        )
        self.tbl_favorites = self.favorites_panel.findChild(QTableWidget)
        self._add_panel("favorites", self.favorites_panel)

        self.savings_panel = self._section(tr("cockpit.panel.savings"))
        self.savings_layout = QVBoxLayout(self.savings_panel)
        self.savings_layout.setContentsMargins(10, 28, 10, 10)
        self._add_panel("savings", self.savings_panel)

        self.warnings_panel = self._table_section(
            tr("cockpit.panel.warnings"),
            [
                tr("col.status"),
                tr("col.typ"),
                tr("col.kategorie"),
                tr("col.budget"),
                tr("col.gebucht"),
            ],
        )
        self.tbl_warnings = self.warnings_panel.findChild(QTableWidget)
        self.tbl_warnings.itemDoubleClicked.connect(
            lambda *_: self.budget_warnings_requested.emit()
        )
        self._add_panel("warnings", self.warnings_panel)

        self.budget_warnings_panel = self._table_section(
            tr("cockpit.panel.budget_warnings"),
            [
                tr("col.typ"),
                tr("col.kategorie"),
                tr("col.budget"),
                tr("col.gebucht"),
                tr("col.auslastung"),
                tr("col.empfehlung"),
            ],
        )
        self.tbl_budget_warnings = self.budget_warnings_panel.findChild(QTableWidget)
        self.tbl_budget_warnings.itemDoubleClicked.connect(
            lambda *_: self.budget_warnings_requested.emit()
        )
        self._add_panel("budget_warnings", self.budget_warnings_panel)

        self.missing_panel = self._table_section(
            tr("cockpit.panel.missing"),
            [
                tr("col.typ"),
                tr("col.kategorie"),
                tr("col.faelligkeit"),
                tr("col.rest"),
                tr("col.aktion"),
            ],
        )
        self.tbl_missing = self.missing_panel.findChild(QTableWidget)
        self.tbl_missing.itemDoubleClicked.connect(
            lambda *_: self.fixcost_requested.emit()
        )
        self._add_panel("missing", self.missing_panel)

        self.recent_panel = self._table_section(
            tr("cockpit.panel.recent"),
            [
                tr("col.datum"),
                tr("col.typ"),
                tr("col.kategorie"),
                tr("col.betrag"),
                tr("col.bemerkung"),
            ],
        )
        self.tbl_recent = self.recent_panel.findChild(QTableWidget)
        self.tbl_recent.itemDoubleClicked.connect(
            lambda *_: self.goto_tracking_requested.emit()
        )
        self._add_panel("recent", self.recent_panel)

        self.body_layout.addStretch(1)
        self._apply_panel_order()
        self._apply_panel_visibility()

    def _section(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl = QLabel(title, frame)
        lbl.move(10, 6)
        lbl.setStyleSheet("font-weight: 700;")
        return frame

    def _table_section(self, title: str, headers: list[str]) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 10)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: 700;")
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        table.setWordWrap(False)
        table.setMinimumHeight(150)
        table.setMinimumWidth(640)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(QHeaderView.Interactive)
        lay.addWidget(lbl)
        lay.addWidget(table)
        return frame

    def _add_panel(self, key: str, widget: QWidget) -> None:
        self._panel_widgets[key] = widget
        self.body_layout.addWidget(widget)

    # ── Public API ───────────────────────────────────────────────
    def _panel_title(self, key: str) -> str:
        return tr(self.PANEL_TITLE_KEYS.get(key, key))

    def get_panel_specs(self) -> list[tuple[str, str]]:
        return [(k, self._panel_title(k)) for k in self._panel_order()]

    def set_panel_visible(self, key: str, visible: bool) -> None:
        cfg = self.settings.get("cockpit_visible_panels", {}) or {}
        cfg = {**self.PANEL_DEFAULTS, **cfg}
        cfg[key] = bool(visible)
        self.settings.set("cockpit_visible_panels", cfg)
        self._apply_panel_visibility()

    def refresh(self) -> None:
        today = date.today()
        y, m = today.year, today.month
        self._refresh_kpis(y, m)
        self._refresh_favorites(y, m)
        self._refresh_savings()
        self._refresh_warnings(y, m)
        self._refresh_budget_warnings(y, m)
        self._refresh_missing(y, m)
        self._refresh_recent()
        self._apply_panel_visibility()

    # ── Refresh helpers ──────────────────────────────────────────
    def _sum_budget_actual(
        self, y: int, m: int, typ: str, category: str | None = None
    ) -> tuple[float, float]:
        start, end = month_bounds(y, m)
        params_b: list[object] = [y, m, typ]
        params_a: list[object] = [start, end, typ]
        q_b = "SELECT COALESCE(SUM(amount),0) FROM budget WHERE year=? AND month=? AND typ=?"
        q_a = "SELECT COALESCE(SUM(amount),0) FROM tracking WHERE date>=? AND date<? AND typ=?"
        if category:
            q_b += " AND category=?"
            params_b.append(category)
            q_a += " AND category=?"
            params_a.append(category)
        b = float(self.conn.execute(q_b, params_b).fetchone()[0] or 0)
        a = float(self.conn.execute(q_a, params_a).fetchone()[0] or 0)
        return b, a

    def _refresh_kpis(self, y: int, m: int) -> None:
        income_b, income_a = self._sum_budget_actual(y, m, TYP_INCOME)
        exp_b, exp_a = self._sum_budget_actual(y, m, TYP_EXPENSES)
        sav_b, sav_a = self._sum_budget_actual(y, m, TYP_SAVINGS)
        self.card_income.set_values(
            format_money(income_a),
            tr("cockpit.kpi_budget").format(amount=format_money(income_b)),
        )
        self.card_expenses.set_values(
            format_money(exp_a),
            tr("cockpit.kpi_budget").format(amount=format_money(exp_b)),
        )
        self.card_savings.set_values(
            format_money(sav_a),
            tr("cockpit.kpi_budget").format(amount=format_money(sav_b)),
        )
        rest = income_a - exp_a - sav_a
        hint = (
            tr("cockpit.balance_positive")
            if rest >= 0
            else tr("cockpit.balance_warning")
        )
        self.card_balance.set_values(format_money(rest), hint)

    def _set_table_rows(
        self, table: QTableWidget, rows: Iterable[Iterable[str]], empty_text: str
    ) -> None:
        rows = list(rows)
        if not rows:
            table.setRowCount(1)
            table.setColumnCount(max(table.columnCount(), 1))
            item = QTableWidgetItem(empty_text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(0, 0, item)
            for c in range(1, table.columnCount()):
                table.setItem(0, c, QTableWidgetItem(""))
            self._stabilize_table_columns(table)
            return
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(r, c, item)
        self._stabilize_table_columns(table)

    def _stabilize_table_columns(self, table: QTableWidget) -> None:
        """Robuste Cockpit-Tabellenbreiten für Windows/Linux/macOS + HiDPI.

        QHeaderView.Stretch kann bei leeren/kurzen Tabellen in Frozen-Builds
        unter Windows sehr kleine Header-Sektionen liefern. Wir setzen deshalb
        bewusst Mindestbreiten und lassen die letzte Spalte den Rest füllen.
        """
        try:
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(True)
            fm = table.fontMetrics()
            for c in range(table.columnCount()):
                text = (
                    table.horizontalHeaderItem(c).text()
                    if table.horizontalHeaderItem(c)
                    else ""
                )
                min_w = max(72, fm.horizontalAdvance(str(text)) + 28)
                # Kategorie/Bemerkung/Empfehlung brauchen auf skalierten Displays mehr Platz.
                if c in (1, table.columnCount() - 1):
                    min_w = max(min_w, 140)
                table.setColumnWidth(c, min_w)
        except Exception as exc:
            logger.debug(
                "Cockpit-Tabellenspalten konnten nicht stabilisiert werden: %s", exc
            )

    def _refresh_favorites(self, y: int, m: int) -> None:
        favs = FavoritesModel(self.conn).list_all()[:12]
        rows = []
        for typ, cat in favs:
            b, a = self._sum_budget_actual(y, m, typ, cat)
            # Für Einnahmen ist Rest = Ist-Budget; für Ausgaben/Ersparnisse Budget-Ist.
            rest = (a - b) if typ == TYP_INCOME else (b - a)
            rows.append(
                [
                    display_typ(typ),
                    cat,
                    format_money(b),
                    format_money(a),
                    format_money(rest),
                ]
            )
        self._set_table_rows(self.tbl_favorites, rows, tr("cockpit.empty_favorites"))

    def _refresh_savings(self) -> None:
        # Inhalt leeren, Titel-Label bleibt das erste Kind nicht zuverlässig; daher alle Widgets aus Layout entfernen.
        while self.savings_layout.count():
            item = self.savings_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        goals = [
            g
            for g in SavingsGoalsModel(self.conn).list_all()
            if getattr(g, "status", STATUS_SAVING) in (STATUS_SAVING, STATUS_RELEASED)
        ][:6]
        if not goals:
            lbl = QLabel(tr("cockpit.no_active_savings"))
            lbl.setWordWrap(True)
            self.savings_layout.addWidget(lbl)
            return
        for g in goals:
            row = QHBoxLayout()
            lbl = QLabel(f"🎯 {g.name}")
            lbl.setMinimumWidth(180)
            bar = QProgressBar()
            target = float(getattr(g, "target_amount", 0) or 0)
            current = float(getattr(g, "current_amount", 0) or 0)
            pct = (
                int(max(0, min(100, round((current / target) * 100))))
                if target > 0
                else 0
            )
            bar.setValue(pct)
            bar.setFormat(f"{pct}% · {format_money(current)} / {format_money(target)}")
            btn = QPushButton(tr("cockpit.open"))
            btn.clicked.connect(self.savings_requested.emit)
            row.addWidget(lbl)
            row.addWidget(bar, 1)
            row.addWidget(btn)
            self.savings_layout.addLayout(row)

    def _refresh_warnings(self, y: int, m: int) -> None:
        rows = []
        start, end = month_bounds(y, m)
        sql = """
            WITH actuals AS (
                SELECT typ, category, SUM(amount) AS actual
                FROM tracking
                WHERE date>=? AND date<?
                GROUP BY typ, category
            )
            SELECT b.typ, b.category, COALESCE(SUM(b.amount),0) AS budget,
                   COALESCE(a.actual,0) AS actual
            FROM budget b
            LEFT JOIN actuals a ON a.typ=b.typ AND a.category=b.category
            WHERE b.year=? AND b.month=?
            GROUP BY b.typ, b.category
            HAVING budget > 0
            ORDER BY b.typ, b.category
        """
        for typ, cat, budget, actual in self.conn.execute(
            sql, (start, end, y, m)
        ).fetchall():
            budget = float(budget or 0)
            actual = float(actual or 0)
            status = None
            if typ == TYP_EXPENSES:
                if actual > budget:
                    status = "🔴 " + tr("cockpit.warning_exceeded")
                elif actual <= budget * 0.1:
                    status = "🟡 " + tr("cockpit.warning_underused")
            elif typ in (TYP_INCOME, TYP_SAVINGS):
                if actual < budget:
                    status = "🟡 " + tr("cockpit.warning_goal_open")
            if status:
                rows.append(
                    [
                        status,
                        display_typ(typ),
                        cat,
                        format_money(budget),
                        format_money(actual),
                    ]
                )
            if len(rows) >= 10:
                break
        self._set_table_rows(self.tbl_warnings, rows, tr("cockpit.empty_warnings"))

    def _refresh_budget_warnings(self, y: int, m: int) -> None:
        """Echte Budgetwarnungen (schwellenbasiert, mit Empfehlung) im Cockpit.

        Nutzt dieselbe Engine wie der Budget-Anpassungsdialog
        (BudgetWarningsModelExtended). Zeigt überschrittene Budgets, nach
        Auslastung absteigend, inkl. vorgeschlagenem Budget.
        """
        excs = []
        try:
            if self._warnings_model_ext is None:
                self._warnings_model_ext = BudgetWarningsModelExtended(self.conn)
            excs = self._warnings_model_ext.check_warnings_extended(
                y, m, lookback_months=6
            )
        except Exception as e:
            logger.debug("budget_warnings: %s", e)
            excs = []

        excs = sorted(
            excs,
            key=lambda e: float(getattr(e, "percent_used", 0.0) or 0.0),
            reverse=True,
        )
        rows = []
        for exc in excs[:10]:
            pct = float(getattr(exc, "percent_used", 0.0) or 0.0)
            cnt = int(getattr(exc, "exceed_count", 0) or 0)
            auslastung = f"{pct:.0f}%" + (f" ({cnt}×)" if cnt > 1 else "")
            sug = getattr(exc, "suggestion", None)
            empfehlung = format_money(float(sug)) if sug else "—"
            rows.append(
                [
                    display_typ(getattr(exc, "typ", "")),
                    str(getattr(exc, "category", "")),
                    format_money(float(getattr(exc, "budget", 0.0) or 0.0)),
                    format_money(float(getattr(exc, "spent", 0.0) or 0.0)),
                    auslastung,
                    empfehlung,
                ]
            )
        self._set_table_rows(
            self.tbl_budget_warnings, rows, tr("cockpit.empty_budget_warnings")
        )

    def _refresh_missing(self, y: int, m: int) -> None:
        rows = []
        sql = """
            SELECT typ, name, COALESCE(is_fix,0) AS is_fix,
                   COALESCE(is_recurring,0) AS is_recurring,
                   COALESCE(recurring_day, 1) AS day
            FROM categories
            WHERE COALESCE(is_fix,0)=1 OR COALESCE(is_recurring,0)=1
            ORDER BY typ, recurring_day, name
        """
        start, end = month_bounds(y, m)
        budgets = {
            (str(r[0]), str(r[1])): float(r[2] or 0.0)
            for r in self.conn.execute(
                """
                SELECT typ, category, COALESCE(SUM(amount),0) AS amount
                FROM budget
                WHERE year=? AND month=?
                GROUP BY typ, category
                """,
                (y, m),
            ).fetchall()
        }
        booked_totals = {
            (str(r[0]), str(r[1])): float(r[2] or 0.0)
            for r in self.conn.execute(
                """
                SELECT typ, category, COALESCE(SUM(amount),0) AS amount
                FROM tracking
                WHERE date>=? AND date<?
                GROUP BY typ, category
                """,
                (start, end),
            ).fetchall()
        }
        EPS = 1e-6
        for typ, name, is_fix, is_recurring, day in self.conn.execute(sql).fetchall():
            is_fix = bool(is_fix)
            is_recurring = bool(is_recurring)
            budget = budgets.get((str(typ), str(name)), 0.0)
            booked = booked_totals.get((str(typ), str(name)), 0.0)

            both_flags = is_fix and is_recurring
            open_item = False
            rest = 0.0
            if both_flags:
                # fixer Monatsbetrag: offen, solange nichts gebucht
                if abs(booked) < EPS:
                    open_item = True
                    rest = budget
            else:
                # fix XOR wiederkehrend: offen, solange Budget im Monat nicht erreicht
                if budget > EPS and abs(booked) < abs(budget) - EPS:
                    open_item = True
                    rest = budget - booked

            if open_item:
                rows.append(
                    [
                        display_typ(typ),
                        name,
                        str(day or 1),
                        format_money(rest),
                        tr("cockpit.doubleclick_book"),
                    ]
                )
            if len(rows) >= 10:
                break
        self._set_table_rows(self.tbl_missing, rows, tr("cockpit.empty_missing"))

    def _refresh_recent(self) -> None:
        rows = []
        cur = self.conn.execute(
            "SELECT date, typ, category, amount, COALESCE(details,'') FROM tracking ORDER BY date DESC, id DESC LIMIT 10"
        )
        for d, typ, cat, amount, details in cur.fetchall():
            rows.append(
                [d, display_typ(typ), cat, format_money(float(amount or 0)), details]
            )
        self._set_table_rows(self.tbl_recent, rows, tr("cockpit.empty_recent"))

    # ── Panel-Reihenfolge ───────────────────────────────────────
    def _panel_order(self) -> list[str]:
        raw = self.settings.get("cockpit_panel_order", None)
        if not isinstance(raw, list):
            raw = list(self.PANEL_ORDER_DEFAULTS)
        order: list[str] = []
        for key in raw:
            if key in self.PANEL_DEFAULTS and key not in order:
                order.append(key)
        for key in self.PANEL_ORDER_DEFAULTS:
            if key not in order:
                order.append(key)
        return order

    def _set_panel_order(self, order: list[str]) -> None:
        clean: list[str] = []
        for key in order:
            if key in self.PANEL_DEFAULTS and key not in clean:
                clean.append(key)
        for key in self.PANEL_ORDER_DEFAULTS:
            if key not in clean:
                clean.append(key)
        self.settings.set("cockpit_panel_order", clean)
        self._apply_panel_order()
        self._apply_panel_visibility()

    def _apply_panel_order(self) -> None:
        # Layout-Struktur: Header an Position 0, danach Panels, am Ende Stretch.
        order = self._panel_order()
        for widget in self._panel_widgets.values():
            self.body_layout.removeWidget(widget)
        insert_at = 1
        for key in order:
            widget = self._panel_widgets.get(key)
            if widget is not None:
                self.body_layout.insertWidget(insert_at, widget)
                insert_at += 1

    # ── Panel visibility ────────────────────────────────────────
    def _panel_config(self) -> dict[str, bool]:
        cfg = self.settings.get("cockpit_visible_panels", {}) or {}
        return {**self.PANEL_DEFAULTS, **cfg}

    def _apply_panel_visibility(self) -> None:
        cfg = self._panel_config()
        for key, widget in self._panel_widgets.items():
            # Sparziele und Favoriten dürfen trotz Default verschwinden, wenn keine Daten vorhanden sind.
            visible = bool(cfg.get(key, True))
            if key == "savings":
                try:
                    has_goals = any(
                        getattr(g, "status", STATUS_SAVING)
                        in (STATUS_SAVING, STATUS_RELEASED)
                        for g in SavingsGoalsModel(self.conn).list_all()
                    )
                    visible = visible and has_goals
                except Exception:
                    pass
            widget.setVisible(visible)

    def _show_customize_menu(self) -> None:
        """Cockpit-Bereiche ein-/ausblenden und Reihenfolge sortieren."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("cockpit.customize_title"))
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)

        info = QLabel(tr("cockpit.customize_intro"))
        info.setWordWrap(True)
        lay.addWidget(info)

        lst = QListWidget()
        lst.setAlternatingRowColors(True)
        cfg = self._panel_config()
        for key in self._panel_order():
            item = QListWidgetItem(self._panel_title(key))
            item.setData(Qt.UserRole, key)
            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
            item.setCheckState(Qt.Checked if bool(cfg.get(key, True)) else Qt.Unchecked)
            lst.addItem(item)
        lay.addWidget(lst, 1)

        row = QHBoxLayout()
        btn_up = QPushButton(tr("cockpit.move_up"))
        btn_down = QPushButton(tr("cockpit.move_down"))
        btn_all = QPushButton(tr("cockpit.show_all"))
        btn_reset = QPushButton(tr("cockpit.reset_order"))
        row.addWidget(btn_up)
        row.addWidget(btn_down)
        row.addStretch(1)
        row.addWidget(btn_all)
        row.addWidget(btn_reset)
        lay.addLayout(row)

        def move(delta: int) -> None:
            r = lst.currentRow()
            nr = r + delta
            if r < 0 or nr < 0 or nr >= lst.count():
                return
            item = lst.takeItem(r)
            lst.insertItem(nr, item)
            lst.setCurrentRow(nr)

        def show_all() -> None:
            for i in range(lst.count()):
                lst.item(i).setCheckState(Qt.Checked)

        def reset_order() -> None:
            states = {}
            for i in range(lst.count()):
                item = lst.item(i)
                states[item.data(Qt.UserRole)] = item.checkState()
            lst.clear()
            for key in self.PANEL_ORDER_DEFAULTS:
                item = QListWidgetItem(self._panel_title(key))
                item.setData(Qt.UserRole, key)
                item.setFlags(
                    item.flags()
                    | Qt.ItemIsUserCheckable
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsEnabled
                )
                item.setCheckState(states.get(key, Qt.Checked))
                lst.addItem(item)

        btn_up.clicked.connect(lambda: move(-1))
        btn_down.clicked.connect(lambda: move(1))
        btn_all.clicked.connect(show_all)
        btn_reset.clicked.connect(reset_order)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        order: list[str] = []
        new_cfg = dict(self.PANEL_DEFAULTS)
        for i in range(lst.count()):
            item = lst.item(i)
            key = item.data(Qt.UserRole)
            order.append(key)
            new_cfg[key] = item.checkState() == Qt.Checked
        self.settings.set("cockpit_visible_panels", new_cfg)
        self._set_panel_order(order)

    def _show_all_panels(self) -> None:
        self.settings.set("cockpit_visible_panels", dict(self.PANEL_DEFAULTS))
        self._apply_panel_visibility()
