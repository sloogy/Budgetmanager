"""Budget-Panel der Finanzübersicht: 3 Tabs (Budgetübersicht, Tabellarisch, Budget-Tabelle).

Extrahiert aus overview_tab.py (v1.0.5 – Patch C: Aufspaltung).

Verantwortlich für:
- Tab 1: Budgetübersicht mit Monatsübertrag (tbl_budget_overview)
- Tab 2: Tabellarischer Kategorie-Baum (tree_maincats + Warnbanner)
- Tab 3: Budget-Tabelle (Budget/Ist/Rest pro Monat, tbl_budget_table)
- Vorschläge-Banner + Suggestions-Dialog
- Kategorie-Baum Logik (Hierarchie-Aufbau, Drill-Down-Vorbereitung)

Schnittstelle zu OverviewTab:
    panel = OverviewBudgetPanel(conn, budget_model, budget_overview, settings, parent=self)
    panel.build_tabs()   → gibt QTabWidget zurück
    panel.refresh(date_from, date_to, year, month_idx, cat_caches, typ_filter)
    panel.overrun_details_requested.connect(...)
    panel.suggestions_requested.connect(...)
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from datetime import date
from typing import Callable

from PySide6.QtCore import Qt, Signal, QSignalBlocker, QObject
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QPushButton, QSizePolicy, QAbstractItemView, QHeaderView, QMessageBox,
)

from model.budget_model import BudgetModel
from model.budget_overview_model import BudgetOverviewModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
from settings import Settings
from utils.i18n import tr, trf, display_typ, db_typ_from_display, tr_category_name
from utils.money import format_money as format_chf, parse_money
from views.ui_colors import ui_colors

from model.typ_constants import normalize_typ as _norm, TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


def _month_label(idx: int) -> str:
    return tr("lbl.entire_year") if idx <= 0 else tr(f"month_short.{idx}")


def _month_range(y: int, m: int) -> tuple[date, date]:
    import calendar
    last = calendar.monthrange(y, m)[1]
    return (date(y, m, 1), date(y, m, last))


class OverviewBudgetPanel(QObject):
    """Logik-Container für Budget-Ansichten.

    Baut 3 eigenständige QWidget-Instanzen, die direkt in das äussere
    budget_tabs-QTabWidget (OverviewTab) eingehängt werden:
        self.w_budget_overview  → Budgetübersicht mit Übertrag
        self.w_tabular          → Kategorie-Baum
        self.w_budget_table     → Budget/Ist/Rest-Tabelle

    Signale können normal mit .connect() verdrahtet werden.
    """

    overrun_details_requested = Signal(list)   # list[dict] mit Überläufen
    suggestions_dialog_requested = Signal()     # Vorschläge-Dialog öffnen
    budget_overview_edit_requested = Signal(str, str)  # typ, category
    budget_data_changed = Signal()              # Budget in DB wurde geändert

    def __init__(self, conn: sqlite3.Connection, budget: BudgetModel,
                 budget_overview: BudgetOverviewModel, settings: Settings,
                 parent=None):
        super().__init__(parent)
        self.conn = conn
        self.budget = budget
        self.budget_overview = budget_overview
        self.settings = settings
        self._budget_table_months: list[tuple[int, int]] = []
        self._last_suggestions: list = []
        self._bo_rendering = False
        self._bo_year = date.today().year
        self._bo_month_idx = date.today().month
        self._bo_single_month = False
        self._bo_show_typ = False
        self._bo_budget_col = -1

        # 3 fertige Widget-Instanzen für das äussere Tab-Widget
        self.w_budget_overview = self._build_budget_overview_tab()
        self.w_tabular         = self._build_tabular_tab()
        self.w_budget_table    = self._build_budget_table_tab()

    def _build_budget_overview_tab(self) -> QWidget:
        """Tab 1: Budgetübersicht mit Übertrag."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(tr("lbl.type")))
        self.bo_typ_combo = QComboBox()
        self.bo_typ_combo.addItems([tr("lbl.all"), display_typ(TYP_EXPENSES),
                                    display_typ(TYP_SAVINGS), display_typ(TYP_INCOME)])
        self.bo_typ_combo.setFixedWidth(130)
        toolbar.addWidget(self.bo_typ_combo)
        toolbar.addWidget(QLabel(tr("overview.lbl.view")))
        self.bo_filter_combo = QComboBox()
        self.bo_filter_combo.addItems([tr("lbl.all"), tr("overview.filter.only_deviations")])
        self.bo_filter_combo.setFixedWidth(150)
        self.bo_filter_combo.setToolTip(tr("overview.tip.bo_filter"))
        toolbar.addWidget(self.bo_filter_combo)
        toolbar.addStretch()
        self.btn_show_suggestions = QPushButton(tr("overview.btn.suggestions"))
        self.btn_show_suggestions.setToolTip(tr("overview.tip.suggestions"))
        self.btn_show_suggestions.clicked.connect(self.suggestions_dialog_requested)
        toolbar.addWidget(self.btn_show_suggestions)
        lay.addLayout(toolbar)

        # Erklärungstext (nur Einzelmonat)
        self.lbl_bo_explain = QLabel()
        self.lbl_bo_explain.setWordWrap(True)
        self.lbl_bo_explain.setVisible(False)
        lay.addWidget(self.lbl_bo_explain)

        # Vorschläge-Banner
        self.lbl_suggestions_banner = QLabel()
        self.lbl_suggestions_banner.setWordWrap(True)
        self.lbl_suggestions_banner.setVisible(False)
        self.lbl_suggestions_banner.setTextFormat(Qt.RichText)
        self.lbl_suggestions_banner.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lbl_suggestions_banner.setOpenExternalLinks(False)
        self.lbl_suggestions_banner.linkActivated.connect(
            lambda lnk: self.suggestions_dialog_requested.emit() if lnk == "details" else None
        )
        lay.addWidget(self.lbl_suggestions_banner)

        # Tabelle
        self.tbl_budget_overview = QTableWidget()
        self.tbl_budget_overview.setAlternatingRowColors(True)
        self.tbl_budget_overview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_budget_overview.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.tbl_budget_overview.verticalHeader().setVisible(False)
        self.tbl_budget_overview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tbl_budget_overview.setMinimumHeight(260)
        self.tbl_budget_overview.cellDoubleClicked.connect(self._on_budget_overview_cell_double_clicked)
        self.tbl_budget_overview.itemChanged.connect(self._on_budget_overview_item_changed)
        lay.addWidget(self.tbl_budget_overview, 1)

        # Zusammenfassung
        self.lbl_bo_summary = QLabel()
        self.lbl_bo_summary.setTextFormat(Qt.RichText)
        self.lbl_bo_summary.setWordWrap(True)
        self.lbl_bo_summary.setStyleSheet("padding: 4px; font-size: 12px;")
        lay.addWidget(self.lbl_bo_summary)
        return w

    def _build_tabular_tab(self) -> QWidget:
        """Tab 2: Kategorie-Baum mit Warnbanner."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Warnbanner
        self.lbl_overrun_banner = QLabel()
        self.lbl_overrun_banner.setWordWrap(True)
        self.lbl_overrun_banner.setVisible(False)
        self.lbl_overrun_banner.setTextFormat(Qt.RichText)
        self.lbl_overrun_banner.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lbl_overrun_banner.setOpenExternalLinks(False)
        _bc = ui_colors(self)
        self.lbl_overrun_banner.setStyleSheet(
            f"padding: 8px; background-color: {_bc.warning_bg}; border-left: 4px solid {_bc.warning}; "
            f"border-radius: 4px; color: {_bc.warning_text};"
        )
        self.lbl_overrun_banner.linkActivated.connect(
            lambda lnk: self.overrun_details_requested.emit(list(self._last_budget_overruns))
            if lnk == "details" else None
        )
        self._last_budget_overruns: list[dict] = []
        lay.addWidget(self.lbl_overrun_banner)

        # Kategorie-Baum
        self.tree_maincats = QTreeWidget()
        self.tree_maincats.setColumnCount(6)
        self.tree_maincats.setHeaderLabels([tr("header.type"), tr("header.category"), tr("header.budget"), tr("lbl.gebucht"), tr("lbl.rest"), "%"])
        self.tree_maincats.setAlternatingRowColors(True)
        self.tree_maincats.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_maincats.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_maincats.setRootIsDecorated(True)
        self.tree_maincats.setIndentation(18)
        self.tree_maincats.setAnimated(True)

        hdr = self.tree_maincats.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4, 5):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        lay.addWidget(self.tree_maincats)
        return w

    def _build_budget_table_tab(self) -> QWidget:
        """Tab 3: Budget/Ist/Rest-Tabelle über mehrere Monate."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # Monatsfenster-Steuerung
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel(tr("lbl.month_window")))
        self.month_window_combo = QComboBox()
        self.month_window_combo.addItems([
            tr("overview.window.selection"),
            tr("overview.window.next"),
            tr("overview.window.prev2"),
            tr("overview.window.prev3"),
        ])
        self.month_window_combo.setFixedWidth(200)
        ctrl.addWidget(self.month_window_combo)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.tbl_budget_table = QTableWidget()
        self.tbl_budget_table.setAlternatingRowColors(True)
        self.tbl_budget_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_budget_table.verticalHeader().setVisible(True)
        self.tbl_budget_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.tbl_budget_table)
        return w

    # ── Externe Signale für Interaktivität ───────────────────────────────────

    def connect_double_clicks(self, on_budget_cell, on_tree_item) -> None:
        """Verbindet Doppelklick-Callbacks vom Orchestrator."""
        self.tbl_budget_table.cellDoubleClicked.connect(on_budget_cell)
        self.tree_maincats.itemDoubleClicked.connect(on_tree_item)
        self.tree_maincats.itemClicked.connect(
            lambda item, col: item.setExpanded(not item.isExpanded()) if item.childCount() > 0 else None
        )

    def connect_filter_signals(self, on_change: Callable) -> None:
        """Verbindet bo_typ_combo und bo_filter_combo mit einem Callback."""
        self.bo_typ_combo.currentIndexChanged.connect(on_change)
        self.bo_filter_combo.currentIndexChanged.connect(on_change)

    def _on_budget_overview_cell_double_clicked(self, row: int, col: int) -> None:
        """Doppelklick in Budgetübersicht: in Budget-Tab zur Bearbeitung springen."""
        try:
            if row < 0:
                return
            # Bei Einzelmonat ist die Budget-Spalte direkt editierbar.
            if self._bo_single_month and col == self._bo_budget_col:
                return
            typ_idx = 0 if self.bo_typ_combo.currentText() == tr("lbl.all") else -1
            cat_idx = 1 if typ_idx == 0 else 0
            cat_item = self.tbl_budget_overview.item(row, cat_idx)
            if not cat_item:
                return
            typ = str(cat_item.data(Qt.UserRole) or "")
            cat = str(cat_item.data(Qt.UserRole + 1) or "")
            if typ and cat:
                self.budget_overview_edit_requested.emit(typ, cat)
        except Exception as e:
            logger.debug("_on_budget_overview_cell_double_clicked: %s", e)

    def _on_budget_overview_item_changed(self, item: QTableWidgetItem) -> None:
        """Inline-Edit der Budget-Spalte (nur Einzelmonat) in DB schreiben."""
        try:
            if self._bo_rendering:
                return
            if not item or not self._bo_single_month:
                return
            if item.column() != self._bo_budget_col or self._bo_month_idx <= 0:
                return
            typ = str(item.data(Qt.UserRole) or "")
            cat = str(item.data(Qt.UserRole + 1) or "")
            if not typ or not cat:
                return

            old_val = float(item.data(Qt.UserRole + 2) or 0.0)
            new_val = float(parse_money(item.text()))
            if abs(new_val - old_val) < 0.0005:
                return

            self.budget.set_amount(self._bo_year, self._bo_month_idx, typ, cat, new_val)
            self.budget_data_changed.emit()
        except Exception as e:
            logger.debug("_on_budget_overview_item_changed: %s", e)

    # ── Daten laden ─────────────────────────────────────────────────────────

    def refresh_budget_overview(
        self, year: int, month_idx: int,
        cat_caches: dict,   # _cat_name_to_id, etc.
    ) -> None:
        """Budgetübersicht-Tab (Tab 1) neu laden."""
        typ_sel_display = self.bo_typ_combo.currentText()
        typ_sel = tr("lbl.all") if typ_sel_display == tr("lbl.all") else db_typ_from_display(typ_sel_display)
        show_all = (self.bo_filter_combo.currentIndex() == 0)

        typen = ([TYP_EXPENSES, TYP_SAVINGS, TYP_INCOME]
                 if typ_sel == tr("lbl.all") else [typ_sel])
        single_month = (month_idx > 0)
        months = [month_idx] if single_month else list(range(1, 13))

        cat_rows, _, _ = self._collect_budget_overview_data(
            year, typen, typ_sel, months, month_idx, single_month, show_all
        )
        self._render_budget_overview_table(cat_rows, year, typ_sel, month_idx, single_month)
        self._render_budget_overview_summary(cat_rows, year, typ_sel, month_idx)
        self._update_suggestions_banner(year, month_idx)

    def refresh_tabular(
        self, date_from: date, date_to: date,
        cat_caches: dict,
        typ_filter_display: str,
        range_idx: int,
    ) -> None:
        """Kategorie-Baum (Tab 2) neu laden."""
        months = _months_between(date_from, date_to)
        budget_raw, actual_raw = self._collect_main_cat_data(months, date_from, date_to)

        wanted = None
        if typ_filter_display and typ_filter_display != tr("lbl.all"):
            wanted = db_typ_from_display(typ_filter_display)

        order = {TYP_INCOME: 0, TYP_EXPENSES: 1, TYP_SAVINGS: 2}
        _c = ui_colors(self)
        eps = 1e-9
        memo: dict[int, tuple[float, float]] = {}

        def _tot(cid: int) -> tuple[float, float]:
            if cid in memo:
                return memo[cid]
            typ, name = cat_caches.get("id_to_name_typ", {}).get(cid, ("", ""))
            b = float(budget_raw.get((typ, name), 0.0))
            a = float(actual_raw.get((typ, name), 0.0))
            for ch in cat_caches.get("children", {}).get(cid, []):
                cb, ca = _tot(int(ch))
                b += cb
                a += ca
            memo[cid] = (b, a)
            return memo[cid]

        def _rp(typ: str, b: float, a: float):
            rest = (a - b) if typ == TYP_INCOME else (b - a)
            pct = (a / b * 100.0) if b > 0 else None
            pct_txt = f"{pct:.0f}%" if pct is not None else "—"
            return rest, pct, pct_txt

        def _show(b, a): return abs(b) > eps or abs(a) > eps

        def _add_node(parent, cid: int, is_root: bool = False):
            typ, name = cat_caches.get("id_to_name_typ", {}).get(cid, ("", ""))
            if wanted and typ != wanted:
                return None
            b, a = _tot(cid)
            if not _show(b, a):
                return None
            rest, pct, pct_txt = _rp(typ, b, a)
            cols = [typ if is_root else "", name,
                    format_chf(b), format_chf(a), format_chf(rest), pct_txt]
            item = QTreeWidgetItem(cols)
            item.setData(0, Qt.UserRole, int(cid))
            for col in (2, 3, 4, 5):
                item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
            if is_root:
                f = QFont(); f.setBold(True)
                for col in range(6): item.setFont(col, f)
            bad = (rest < 0) if typ == TYP_INCOME else (rest < 0 or (pct is not None and pct > 100))
            if bad:
                item.setForeground(4, QColor(_c.negative))
                item.setForeground(5, QColor(_c.negative))
            status = "✓ OK"
            if bad:
                status = tr("overview.target_missed") if typ == TYP_INCOME else tr("overview.budget_exceeded")
            tip = trf("tip.budget_cell", typ=typ, name=name, budget=format_chf(b), actual=format_chf(a), rest=format_chf(rest), status=status)
            for col in range(6): item.setToolTip(col, tip)
            if parent is None:
                self.tree_maincats.addTopLevelItem(item)
            else:
                parent.addChild(item)

            children = sorted(
                cat_caches.get("children", {}).get(cid, []),
                key=lambda ch: (order.get(cat_caches.get("id_to_name_typ", {}).get(int(ch), ("",))[0], 9),
                                -(actual_raw.get(cat_caches.get("id_to_name_typ", {}).get(int(ch), ("",""))[1:2], [0])[0] if False else _tot(int(ch))[1]),
                                cat_caches.get("id_to_name_typ", {}).get(int(ch), ("",""))[1].lower() if len(cat_caches.get("id_to_name_typ", {}).get(int(ch), ())) > 1 else "")
            )
            for ch in children:
                _add_node(item, int(ch), is_root=False)
            return item

        self.tree_maincats.clear()
        roots = sorted(
            [int(cid) for cid, pid in cat_caches.get("parent", {}).items() if pid is None],
            key=lambda cid: (order.get(cat_caches.get("id_to_name_typ", {}).get(cid, ("",))[0], 9),
                             -_tot(cid)[1],
                             (cat_caches.get("id_to_name_typ", {}).get(cid, ("",""))[1:2] or [""])[0].lower())
        )
        for cid in roots:
            it = _add_node(None, int(cid), is_root=True)
            if it:
                it.setExpanded(False)

        # Unbekannte Kategorien
        known = set(cat_caches.get("name_to_id", {}).keys())
        unknown = (set(budget_raw.keys()) | set(actual_raw.keys())) - known
        overruns = []
        for (t, name) in unknown:
            if wanted and t != wanted: continue
            b = float(budget_raw.get((t, name), 0.0))
            a = float(actual_raw.get((t, name), 0.0))
            if not _show(b, a): continue
            rest, pct, pct_txt = _rp(t, b, a)
            cols = [t, f"⚠ {name}", format_chf(b), format_chf(a), format_chf(rest), pct_txt]
            item = QTreeWidgetItem(cols)
            for col in (2, 3, 4, 5): item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
            bad = (rest < 0) if t == TYP_INCOME else (rest < 0 or (pct is not None and pct > 100))
            if bad:
                item.setForeground(4, QColor(_c.negative))
                item.setForeground(5, QColor(_c.negative))
            self.tree_maincats.addTopLevelItem(item)
            if bad:
                overruns.append({"typ": t, "category": name, "budget": b, "actual": a, "rest": rest, "pct": pct})

        # Warnbanner aktualisieren
        if range_idx == 0:
            for cid in roots:
                typ, name = cat_caches.get("id_to_name_typ", {}).get(cid, ("", ""))
                b, a = _tot(cid)
                if not _show(b, a): continue
                rest, pct, _ = _rp(typ, b, a)
                bad = (rest < 0) if typ == TYP_INCOME else (rest < 0 or (pct is not None and pct > 100))
                if bad:
                    overruns.append({"typ": typ, "category": name, "budget": b, "actual": a, "rest": rest, "pct": pct})
            self._update_overrun_banner(overruns, date_from=date_from, date_to=date_to)
        else:
            self._update_overrun_banner([])

    def refresh_budget_table(
        self, date_from: date, date_to: date,
        year: int, month_idx: int,
        range_idx: int,
        track,  # TrackingModel
    ) -> None:
        """Budget-Tabelle (Tab 3) neu laden."""
        # Monate bestimmen
        months: list[tuple[int, int]] = []
        try:
            if range_idx == 0:
                if month_idx == 0:
                    months = [(year, m) for m in range(1, 13)]
                else:
                    mode = self.month_window_combo.currentIndex()
                    if mode == 0:
                        months = [(year, month_idx)]
                    elif mode == 1:
                        months = [(year, month_idx)]
                        if month_idx < 12: months.append((year, month_idx + 1))
                    elif mode == 2:
                        months = [(year, m) for m in range(max(1, month_idx - 2), month_idx + 1)]
                    else:
                        months = [(year, m) for m in range(max(1, month_idx - 3), month_idx + 1)]
            else:
                cur = date(date_from.year, date_from.month, 1)
                end = date(date_to.year, date_to.month, 1)
                while cur <= end:
                    months.append((cur.year, cur.month))
                    cur = date(cur.year + (1 if cur.month == 12 else 0),
                               1 if cur.month == 12 else cur.month + 1, 1)
        except Exception:
            months = [(date_from.year, date_from.month)]

        if not months:
            months = [(date_from.year, date_from.month)]

        self._budget_table_months = list(months)

        years_in_months = {y for y, _ in months}
        same_year = len(years_in_months) == 1
        col_labels = [(_month_label(m) if same_year else f"{_month_label(m)} {y}") for y, m in months]

        row_labels = [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]  # DB-Schluessel (nicht uebersetzen)
        _c = ui_colors(self)

        self.tbl_budget_table.clear()
        self.tbl_budget_table.setRowCount(len(row_labels))
        self.tbl_budget_table.setColumnCount(len(months))
        self.tbl_budget_table.setHorizontalHeaderLabels(col_labels)
        self.tbl_budget_table.setVerticalHeaderLabels(row_labels)
        self.tbl_budget_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_budget_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # Tracking einmal laden (O(1)-Lookup statt N×M DB-Calls)
        if months:
            d1, _ = _month_range(months[0][0], months[0][1])
            _, d2 = _month_range(months[-1][0], months[-1][1])
            all_rows = track.get_entries_in_range(d1, d2)
            cache: dict[tuple[int, int], list] = {}
            for tr_row in all_rows:
                key = (tr_row.date.year, tr_row.date.month)
                cache.setdefault(key, []).append(tr_row)
        else:
            cache = {}

        for ri, typ in enumerate(row_labels):
            for ci, (y, m) in enumerate(months):
                try:
                    bsum = float(self.budget.sum_by_typ(y, m).get(typ, 0.0))
                except Exception:
                    bsum = 0.0

                trows = cache.get((y, m), [])
                if typ == TYP_INCOME:
                    asum = sum(r.amount for r in trows if _norm(r.typ) == typ)
                    rest = asum - bsum
                elif typ == TYP_EXPENSES:
                    asum = sum(abs(r.amount) for r in trows if _norm(r.typ) == typ)
                    rest = bsum - asum
                else:
                    asum = sum(r.amount for r in trows if _norm(r.typ) == typ)
                    rest = bsum - asum

                cell = QTableWidgetItem(f"B: {format_chf(bsum)}\nI: {format_chf(asum)}\nR: {format_chf(rest)}")
                cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                cell.setToolTip(
                    f"{typ} – {col_labels[ci]}\n" +
                    trf("tip.budget_table_cell", budget=format_chf(bsum), actual=format_chf(asum), rest=format_chf(rest))
                )
                if rest < 0:
                    cell.setForeground(QColor(_c.negative))
                self.tbl_budget_table.setItem(ri, ci, cell)

        self.tbl_budget_table.resizeRowsToContents()

    # ── Budget-Übersicht Hilfsmethoden ───────────────────────────────────────

    def _collect_budget_overview_data(
        self, year: int, typen: list, typ_sel: str,
        months: list, month_idx: int, single_month: bool, show_all: bool,
    ) -> tuple[list, float, float]:
        suggestion_map: dict[tuple[str, str], float] = {}
        try:
            min_months = int(self.settings.get("budget_suggestion_months", 3) or 3)
            suggs = self.budget_overview.get_suggestions(
                year=year, current_month=month_idx or date.today().month,
                min_consecutive_months=min_months, types=typen,
            )
            for s in suggs:
                suggestion_map[(s.typ, s.category)] = float(s.suggested_amount)
        except Exception:
            pass

        cat_rows, total_budget, total_actual = [], 0.0, 0.0

        for typ in typen:
            try:
                typ_db = db_typ_from_display(typ)
            except Exception:
                typ_db = typ

            try:
                budget_cats = self.budget_overview.budget_by_category_range(year, months, typ_db)
                actual_cats = self.budget_overview.actual_by_category_range(year, months, typ_db)
            except Exception:
                budget_cats, actual_cats = {}, {}

            carry_cats = {}
            if single_month:
                try:
                    co_start = int(self.settings.get("carryover_start_month", 1) or 1)
                    co_year_raw = int(self.settings.get("carryover_start_year", 0) or 0)
                    co_year = co_year_raw if co_year_raw > 0 else year
                    carry_cats = self.budget_overview.carry_over_by_category(
                        year, month_idx, typ_db,
                        start_month=co_start, start_year=co_year
                    )
                except Exception:
                    pass

            for cat in sorted(set(budget_cats) | set(actual_cats) | set(carry_cats)):
                b = budget_cats.get(cat, 0.0)
                a = actual_cats.get(cat, 0.0)
                co = carry_cats.get(cat, 0.0) if single_month else 0.0
                bc = b + co
                inc = is_income(typ_db)
                rest = (a - bc) if inc else (bc - a)
                sugg = suggestion_map.get((typ_db, cat))
                total_budget += b; total_actual += a

                if show_all:
                    if b > 0.01 or a > 0.01 or abs(co) > 0.01:
                        cat_rows.append((typ_db, cat, co, b, bc, a, rest, rest, sugg))
                else:
                    if abs(rest) > 0.01:
                        cat_rows.append((typ_db, cat, co, b, bc, a, rest, rest, sugg))

        return cat_rows, total_budget, total_actual

    def _render_budget_overview_table(
        self, cat_rows: list, year: int, typ_sel: str,
        month_idx: int, single_month: bool,
    ) -> None:
        show_typ = (typ_sel == tr("lbl.all"))
        self._bo_year = int(year)
        self._bo_month_idx = int(month_idx)
        self._bo_single_month = bool(single_month)
        self._bo_show_typ = bool(show_typ)

        if single_month:
            cols = ([tr("header.type")] if show_typ else []) + [
                tr("header.category"), tr("lbl.carryover"), tr("header.budget"),
                tr("lbl.budget_with_carry"), tr("lbl.gebucht"), tr("lbl.rest"),
                tr("lbl.next_carryover"), tr("lbl.suggestion"),
            ]
            self._bo_budget_col = 3 if show_typ else 2
        else:
            cols = ([tr("header.type")] if show_typ else []) + [
                tr("header.category"), tr("header.budget"), tr("lbl.gebucht"), tr("lbl.rest"), tr("lbl.suggestion"),
            ]
            self._bo_budget_col = -1

        # Erklärungstext
        if single_month:
            try:
                sm = int(self.settings.get("carryover_start_month", 1) or 1)
                sy = int(self.settings.get("carryover_start_year", 0) or 0) or year
                self.lbl_bo_explain.setText(
                    trf("tip.carryover_explain", from_month=_month_label(sm), from_year=sy)
                )
            except Exception:
                self.lbl_bo_explain.setText(tr("tip.carryover_short"))
            self.lbl_bo_explain.setVisible(True)
        else:
            self.lbl_bo_explain.setVisible(False)

        tbl = self.tbl_budget_overview
        self._bo_rendering = True
        try:
            with QSignalBlocker(tbl):
                tbl.clear()
                tbl.setColumnCount(len(cols))
                tbl.setRowCount(len(cat_rows))
                tbl.setHorizontalHeaderLabels(cols)

                hdr = tbl.horizontalHeader()
                if show_typ:
                    hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                    hdr.setSectionResizeMode(1, QHeaderView.Stretch)
                    for c in range(2, len(cols)):
                        hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
                else:
                    hdr.setSectionResizeMode(0, QHeaderView.Stretch)
                    for c in range(1, len(cols)):
                        hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)

                monat_text = _month_label(month_idx)
                _c = ui_colors(self)

                for row_idx, (typ, cat, co, b, bc, a, rest, next_carry, sugg) in enumerate(cat_rows):
                    pct = (a / bc * 100) if bc > 0 else (0 if a == 0 else 999)
                    sugg_txt = format_chf(sugg) if sugg is not None else "\u2013"

                    if single_month:
                        vals = (["Typ=" + typ] if show_typ else []) + [
                            cat, format_chf(co), format_chf(b), format_chf(bc),
                            format_chf(a), format_chf(rest), format_chf(next_carry), sugg_txt,
                        ]
                    else:
                        vals = (["Typ=" + typ] if show_typ else []) + [
                            cat, format_chf(b), format_chf(a), format_chf(rest), sugg_txt,
                        ]
                    if show_typ:
                        vals[0] = typ

                    rest_idx = (len(vals) - 3) if single_month else (len(vals) - 2)
                    first_num = 2 if show_typ else 1

                    for col, val in enumerate(vals):
                        item = QTableWidgetItem(val)
                        item.setData(Qt.UserRole, typ)
                        item.setData(Qt.UserRole + 1, cat)
                        if col == self._bo_budget_col:
                            item.setData(Qt.UserRole + 2, float(b))

                        flags = item.flags() & ~Qt.ItemFlag.ItemIsEditable
                        if self._bo_single_month and col == self._bo_budget_col:
                            flags |= Qt.ItemFlag.ItemIsEditable
                        item.setFlags(flags)

                        if col >= first_num:
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        if show_typ and col == 0:
                            item.setForeground(QColor(_c.type_colors.get(typ, _c.text_dim)))
                            f = item.font()
                            f.setBold(True)
                            item.setFont(f)
                        if col == rest_idx:
                            if rest < -0.01:
                                item.setForeground(QColor(_c.negative))
                                f = item.font()
                                f.setBold(True)
                                item.setFont(f)
                            elif rest > 0.01:
                                item.setForeground(QColor(_c.ok))
                        item.setToolTip(
                            f"{cat} \u2013 {typ} ({monat_text} {year})\n"
                            + trf(
                                "tip.budget_overview_cell",
                                budget=format_chf(b),
                                booked=format_chf(a),
                                pct=pct,
                                rest=format_chf(rest),
                            )
                        )
                        tbl.setItem(row_idx, col, item)

                try:
                    tbl.resizeRowsToContents()
                except Exception as e:
                    logger.debug("resizeRowsToContents: %s", e)
        finally:
            self._bo_rendering = False

    def _render_budget_overview_summary(
        self, cat_rows: list, year: int, typ_sel: str, month_idx: int,
    ) -> None:
        monat_text = _month_label(month_idx)
        _c = ui_colors(self)
        n_deficit  = sum(1 for *_, r, _, _s in cat_rows if r < -0.01)
        n_surplus  = sum(1 for *_, r, _, _s in cat_rows if r > 0.01)
        n_even     = len(cat_rows) - n_deficit - n_surplus

        if not cat_rows:
            self.lbl_bo_summary.setVisible(False)
            return

        typ_lbl = tr("lbl.all") if typ_sel == tr("lbl.all") else display_typ(typ_sel)
        html = trf(
            "overview.summary",
            typ=typ_lbl,
            month=monat_text,
            year=year,
            n=len(cat_rows),
            color_neg=_c.negative,
            deficit=n_deficit,
            color_ok=_c.ok,
            surplus=n_surplus,
            balanced=n_even,
        )
        self.lbl_bo_summary.setText(html)
        self.lbl_bo_summary.setVisible(True)

    def _update_suggestions_banner(self, year: int, month_idx: int) -> None:
        try:
            current_month = month_idx if month_idx > 0 else (
                date.today().month if year == date.today().year else 12
            )
            min_months = int(self.settings.get("budget_suggestion_months", 3) or 3)
            suggestions = self.budget_overview.get_suggestions(
                year=year, current_month=current_month,
                min_consecutive_months=min_months,
            )
            type_suggs = self.budget_overview.get_type_suggestions(
                year=year, current_month=current_month,
                min_consecutive_months=min_months,
            )
            all_suggs = type_suggs + suggestions
            self._last_suggestions = all_suggs

            if not all_suggs:
                self.lbl_suggestions_banner.setVisible(False)
                return

            count = len(all_suggs)
            preview = []
            for s in all_suggs[:2]:
                icon = "📈" if s.direction == "surplus" else "📉"
                preview.append(
                    trf(
                        "overview.sugg.preview_item",
                        icon=icon,
                        typ=s.typ,
                        category=tr_category_name(s.category),
                        months=s.consecutive_months,
                    )
                )
            more = trf("overview.sugg.more", n=(count - 2)) if count > 2 else ""

            c = ui_colors(self)
            banner_style = (
                f"padding: 8px; background-color: {c.success_bg}; border-left: 4px solid {c.ok}; "
                f"border-radius: 4px; color: {c.success_text};"
            )
            income_warn = ""
            try:
                coverage = self.budget_overview.check_income_coverage(year, current_month, all_suggs)
                if coverage:
                    income_warn = trf(
                        "overview.sugg.income_exceeded",
                        deficit=format_chf(coverage["deficit"]),
                    )
                    banner_style = (
                        f"padding: 8px; background-color: {c.warning_bg}; border-left: 4px solid {c.warning}; "
                        f"border-radius: 4px; color: {c.warning_text};"
                    )
            except Exception as e:
                logger.debug("check_income_coverage: %s", e)

            plural = "e" if count != 1 else ""
            text = (
                trf("overview.sugg.title", count=count, plural=plural)
                + ", ".join(preview) + more + income_warn
                + f" – <a href='details'>{tr('overview.details_show')}</a>"
            )
            self.lbl_suggestions_banner.setText(text)
            self.lbl_suggestions_banner.setStyleSheet(banner_style)
            self.lbl_suggestions_banner.setVisible(True)

        except Exception as exc:
            logger.warning("suggestions banner: %s", exc)
            self.lbl_suggestions_banner.setVisible(False)

    def _collect_main_cat_data(
        self, months: list[tuple[int, int]], date_from: date, date_to: date,
    ) -> tuple[dict, dict]:
        budget_raw: dict[tuple[str, str], float] = {}
        raw = self.budget.sum_by_typ_category_range(months)
        for (typ_str, cat_str), val in raw.items():
            t = _norm(typ_str)
            budget_raw[(t, cat_str)] = budget_raw.get((t, cat_str), 0.0) + val

        from model.tracking_model import TrackingModel
        # track is not stored; use budget_overview.conn
        try:
            from model.tracking_model import TrackingModel
            track = TrackingModel(self.conn)
            rows = track.get_entries_in_range(date_from, date_to)
        except Exception:
            rows = []

        actual_raw: dict[tuple[str, str], float] = {}
        for r in rows:
            t = _norm(r.typ)
            amt = abs(float(r.amount)) if t == TYP_EXPENSES else float(r.amount)
            actual_raw[(t, r.category)] = actual_raw.get((t, r.category), 0.0) + amt

        return budget_raw, actual_raw

    def _update_overrun_banner(self, overruns: list[dict],
                               date_from: date | None = None,
                               date_to: date | None = None) -> None:
        self._last_budget_overruns = list(overruns or [])
        if not overruns:
            self.lbl_overrun_banner.setVisible(False)
            return

        overruns_sorted = sorted(overruns, key=lambda o: float(o.get("rest", 0.0) or 0.0))
        preview = []
        for o in overruns_sorted[:3]:
            preview.append(f"{tr_category_name(str(o.get('category')))} ({format_chf(float(o.get('rest', 0.0) or 0.0))})")
        extra = trf("overview.sugg.more", n=(len(overruns_sorted) - 3)) if len(overruns_sorted) > 3 else ""

        period = ""
        if date_from and date_to:
            period = f"({date_from:%d.%m.%Y} – {date_to:%d.%m.%Y})"

        self.lbl_overrun_banner.setText(
            trf("overview.overrun.title", period=period)
            + ", ".join(preview) + extra
            + f" – <a href='details'>{tr('overview.details_show')}</a>"
        )
        self.lbl_overrun_banner.setVisible(True)
# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _months_between(d1: date, d2: date) -> list[tuple[int, int]]:
    if d2 < d1: d1, d2 = d2, d1
    cur = date(d1.year, d1.month, 1)
    end = date(d2.year, d2.month, 1)
    out = []
    while cur <= end:
        out.append((cur.year, cur.month))
        cur = date(cur.year + (1 if cur.month == 12 else 0),
                   1 if cur.month == 12 else cur.month + 1, 1)
    return out
