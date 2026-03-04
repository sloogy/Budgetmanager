"""Finanzübersicht-Tab – schlanker Orchestrator (v1.0.5 Patch C).

Zuständig für:
- Layout (Header, Splitter, Sub-Panel-Verkabelung)
- Zeitraum-Steuerung (Range/Jahr/Monat)
- refresh_data() – Daten an Sub-Panels weiterleiten
- Signal-Routing zwischen Sub-Panels

Die eigentliche Logik lebt in den Sub-Modulen:
    overview_widgets.py       – wiederverwendbare UI-Primitives
    overview_kpi_panel.py     – KPI-Cards + Charts
    overview_budget_panel.py  – Budget/Tabellen/Vorschläge
    overview_savings_panel.py – Sparziele
    overview_right_panel.py   – Filter + Transaktionsliste
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from datetime import date, timedelta
import calendar

from PySide6.QtCore import Qt, QTimer, Signal, QDate, QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QFrame, QScrollArea, QGroupBox, QSizePolicy,
    QPushButton, QSplitter, QTabWidget, QMessageBox,
    QTreeWidgetItem,
)

from model.budget_model import BudgetModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, normalize_typ
from model.tracking_model import TrackingModel
from model.category_model import CategoryModel
from model.tags_model import TagsModel
from model.savings_goals_model import SavingsGoalsModel
from model.budget_overview_model import BudgetOverviewModel
from settings import Settings

from utils.icons import get_icon
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from utils.money import format_money as format_chf, currency_header

from views.ui_colors import ui_colors
from views.tabs.overview_kpi_panel import OverviewKpiPanel
from views.tabs.overview_budget_panel import OverviewBudgetPanel, _months_between
from views.tabs.overview_savings_panel import OverviewSavingsPanel
from views.tabs.overview_right_panel import OverviewRightPanel


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _month_label(idx: int) -> str:
    return tr("lbl.entire_year") if idx <= 0 else tr(f"month_short.{idx}")


def _month_items() -> list[str]:
    return [tr("lbl.entire_year")] + [tr(f"month_short.{i}") for i in range(1, 13)]


def _range_items() -> list[str]:
    return [
        tr("overview.range.year_month"),
        trf("overview.range.last_days", n=7),
        trf("overview.range.last_days", n=30),
        trf("overview.range.last_days", n=90),
        tr("overview.range.custom"),
    ]


def _to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _month_range(y: int, m: int) -> tuple[date, date]:
    last = calendar.monthrange(y, m)[1]
    return (date(y, m, 1), date(y, m, last))


from model.typ_constants import normalize_typ as _norm_typ, TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


# ── OverviewTab ──────────────────────────────────────────────────────────────

class OverviewTab(QWidget):
    """Finanzübersicht Tab – Orchestrator."""

    quick_add_requested = Signal()
    budget_warnings_requested = Signal()
    budget_edit_requested = Signal(str, str, int, int)  # typ, category, year, month

    def __init__(self, conn: sqlite3.Connection, settings: Settings | None = None):
        super().__init__()
        self.conn = conn
        self.settings = settings or Settings()

        # Modelle
        self.budget          = BudgetModel(conn)
        self.track           = TrackingModel(conn)
        self.categories      = CategoryModel(conn)
        self.tags            = TagsModel(conn)
        self.savings         = SavingsGoalsModel(conn)
        self.budget_overview = BudgetOverviewModel(conn)

        # Kategorie-Caches (werden in _load_categories() befüllt)
        self._cat_caches: dict = {}
        self._tag_name_to_id: dict[str, int] = {}
        self._descendant_name_cache: dict = {}

        # Refresh-Timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_guarded_refresh)
        self._is_visible = True

        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(100, self.refresh_data)

    # ── Subtab-Visibility API (für MainWindow) ──────────────────────────────

    def get_subtab_specs(self) -> list[tuple[str, str]]:
        return [
            ("kpi",      tr("tab.diagram")),
            ("budget",   tr("tab.budget_overview")),
            ("tabular",  tr("tab.tabular")),
            ("savings",  tr("tab.savings")),
        ]

    def apply_subtab_visibility(self, visibility: dict[str, bool]) -> None:
        specs = self.get_subtab_specs()
        for key, title in specs:
            visible = visibility.get(key, True)
            self.set_subtab_visible(key, visible)

    def set_subtab_visible(self, key: str, visible: bool) -> None:
        idx_map = {"kpi": 0, "budget": 1, "tabular": 2, "budget_table": 3, "savings": 4}
        idx = idx_map.get(key, -1)
        if idx >= 0 and hasattr(self, "budget_tabs"):
            self.budget_tabs.setTabVisible(idx, visible)

    # ── Layout ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        main_layout.addWidget(self._create_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self.main_splitter = QSplitter(Qt.Horizontal)

        # ── Linkes Panel ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # KPI-Panel (KPI-Cards + Progress-Bars sind jetzt direkt im Diagramm-Tab)
        self.kpi_panel = OverviewKpiPanel(self.budget_overview, parent=self)
        self.kpi_panel.kpi_clicked.connect(self._on_kpi_clicked)
        self.kpi_panel.chart_category_clicked.connect(self._on_chart_category_clicked)
        self.kpi_panel.chart_type_clicked.connect(self._on_chart_type_clicked)

        # Budget-Panel (QObject-Logik-Container, kein eigenes Widget)
        self.budget_panel = OverviewBudgetPanel(
            self.conn, self.budget, self.budget_overview, self.settings, parent=self
        )
        self.budget_panel.suggestions_dialog_requested.connect(self._show_budget_suggestions_dialog)
        self.budget_panel.overrun_details_requested.connect(self._show_overrun_details)
        self.budget_panel.budget_overview_edit_requested.connect(self._on_budget_overview_edit_requested)
        self.budget_panel.budget_data_changed.connect(self._delayed_refresh)
        self.budget_panel.connect_double_clicks(
            on_budget_cell=self._on_budget_cell_double_clicked,
            on_tree_item=self._on_maincat_item_double_clicked,
        )
        self.budget_panel.connect_filter_signals(self._delayed_refresh)

        # Sparziele-Panel
        self.savings_panel = OverviewSavingsPanel(self.conn, parent=self)

        # Budget-GroupBox mit 5 Tabs (identische Struktur wie v1.0.4)
        self.budget_group = QGroupBox(tr("grp.budget_vs_actual"))
        bg_layout = QVBoxLayout(self.budget_group)
        bg_layout.setSpacing(4)
        bg_layout.setContentsMargins(4, 4, 4, 4)

        self.budget_tabs = QTabWidget()
        # Tab 0: KPI-Cards + Charts
        self.budget_tabs.addTab(self.kpi_panel,                      tr("tab.diagram"))
        # Tabs 1–3: Direkt die vom OverviewBudgetPanel gebauten QWidget-Instanzen
        self.budget_tabs.addTab(self.budget_panel.w_budget_overview, tr("tab.budget_overview"))
        self.budget_tabs.addTab(self.budget_panel.w_tabular,         tr("tab.tabular"))
        self.budget_tabs.addTab(self.budget_panel.w_budget_table,    tr("tab.budget_table"))
        # Tab 4: Sparziele
        self.budget_tabs.addTab(self.savings_panel,                  tr("tab.savings"))

        bg_layout.addWidget(self.budget_tabs)
        left_layout.addWidget(self.budget_group)
        left_layout.addStretch()

        # ── Rechtes Panel ──
        self.right_panel = OverviewRightPanel(
            self.conn, self.track, self.categories, self.tags, parent=self
        )
        self.right_panel.filters_reset.connect(self.refresh_data)
        self.right_panel.typ_filter_changed.connect(self._delayed_refresh)

        self.main_splitter.addWidget(left)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 6)
        self.main_splitter.setStretchFactor(1, 4)

        self._right_panel_visible = True
        self._splitter_sizes = None

        content_layout.addWidget(self.main_splitter)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header.setMaximumHeight(55)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel(tr("overview.title"))
        font = QFont(); font.setPointSize(12); font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addStretch()

        self.btn_quick_add = QPushButton(tr("budget.btn.quick_add"))
        self.btn_quick_add.setToolTip(tr("budget.tip.quick_add"))
        self.btn_quick_add.clicked.connect(self.quick_add_requested.emit)
        layout.addWidget(self.btn_quick_add)

        layout.addWidget(QLabel(tr("lbl.period")))
        self.range_combo = QComboBox()
        self.range_combo.addItems(_range_items())
        self.range_combo.setFixedWidth(140)
        layout.addWidget(self.range_combo)

        layout.addWidget(QLabel(tr("lbl.year")))
        self.year_combo = QComboBox()
        self._reload_years()
        self.year_combo.setFixedWidth(70)
        layout.addWidget(self.year_combo)

        layout.addWidget(QLabel(tr("lbl.month")))
        self.month_combo = QComboBox()
        self.month_combo.addItems(_month_items())
        self.month_combo.setCurrentIndex(min(date.today().month, 12))
        self.month_combo.setFixedWidth(120)
        layout.addWidget(self.month_combo)

        self.btn_refresh = QPushButton("")
        self.btn_refresh.setIcon(get_icon("🔄"))
        self.btn_refresh.setFixedWidth(35)
        self.btn_refresh.setToolTip(tr("overview.tip.refresh"))
        layout.addWidget(self.btn_refresh)

        self.btn_toggle_right = QPushButton("")
        self.btn_toggle_right.setIcon(get_icon("📋"))
        self.btn_toggle_right.setFixedWidth(35)
        self.btn_toggle_right.setToolTip(tr("overview.tip.toggle_sidebar"))
        self.btn_toggle_right.setCheckable(True)
        self.btn_toggle_right.setChecked(True)
        self.btn_toggle_right.clicked.connect(self._toggle_right_panel)
        layout.addWidget(self.btn_toggle_right)

        return header

    # ── Signal-Verdrahtung ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)
        self.year_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.month_combo.currentIndexChanged.connect(self._delayed_refresh)
        self.month_combo.currentIndexChanged.connect(self._sync_month_window_enabled)

        # Budget-Tabs Wechsel → neu laden
        for tab_widget in (self.budget_tabs, self.kpi_panel.chart_tabs):
            try:
                tab_widget.currentChanged.connect(self._delayed_refresh)
            except Exception as e:
                logger.debug("tab currentChanged connect: %s", e)

        # month_window_combo liegt im budget_panel
        self.budget_panel.month_window_combo.currentIndexChanged.connect(self._delayed_refresh)  # on w_budget_table

        # btn_show_suggestions ist bereits in overview_budget_panel._build_budget_overview_tab()
        # mit suggestions_dialog_requested verbunden → _show_budget_suggestions_dialog.
        # KEINE zweite Verbindung hier, sonst öffnet sich der Dialog doppelt.
        # budget_warnings_requested wird ausschliesslich über das Extras-Menü ausgelöst.

    # ── Zeitraum / Range Logik ───────────────────────────────────────────────

    def _get_date_range(self) -> tuple[date, date]:
        idx = self.range_combo.currentIndex()
        today = date.today()

        if idx == 0:  # Jahr/Monat
            try:
                year = int(self.year_combo.currentText())
            except (ValueError, AttributeError):
                year = today.year
            month_idx = self.month_combo.currentIndex()
            if month_idx == 0:
                return (date(year, 1, 1), date(year, 12, 31))
            else:
                return _month_range(year, month_idx)
        elif idx == 1:
            return (today - timedelta(days=7), today)
        elif idx == 2:
            return (today - timedelta(days=30), today)
        elif idx == 3:
            return (today - timedelta(days=90), today)
        else:  # Custom
            d_from = self.right_panel.date_from.date().toPython()
            d_to   = self.right_panel.date_to.date().toPython()
            return (d_from, d_to)

    def _on_range_changed(self) -> None:
        idx = self.range_combo.currentIndex()
        is_custom = (idx == 4)
        is_ym = (idx == 0)

        self.year_combo.setEnabled(is_ym)
        self.month_combo.setEnabled(is_ym)
        self._sync_month_window_enabled()

        today = date.today()
        if idx == 1:
            self.right_panel.date_from.setDate(_to_qdate(today - timedelta(days=7)))
            self.right_panel.date_to.setDate(_to_qdate(today))
        elif idx == 2:
            self.right_panel.date_from.setDate(_to_qdate(today - timedelta(days=30)))
            self.right_panel.date_to.setDate(_to_qdate(today))
        elif idx == 3:
            self.right_panel.date_from.setDate(_to_qdate(today - timedelta(days=90)))
            self.right_panel.date_to.setDate(_to_qdate(today))

        self._delayed_refresh()

    def _sync_month_window_enabled(self) -> None:
        is_ym = (self.range_combo.currentIndex() == 0)
        self.budget_panel.month_window_combo.setEnabled(
            is_ym and self.month_combo.currentIndex() != 0
        )

    def _reload_years(self) -> None:
        self.year_combo.clear()
        years = self.track.get_available_years()
        if not years:
            years = [date.today().year]
        for y in years:
            self.year_combo.addItem(str(y))
        cy = date.today().year
        idx = years.index(cy) if cy in years else 0
        self.year_combo.setCurrentIndex(idx)

    # ── Daten-Routing ────────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        """Hauptmethode – alle Sub-Panels aktualisieren."""
        self._load_categories()
        self._load_tags()

        date_from, date_to = self._get_date_range()

        try:
            year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            year = date.today().year
        month_idx = self.month_combo.currentIndex()
        range_idx = self.range_combo.currentIndex()

        # Tracking-Rows einmal laden (gemeinsam genutzt)
        try:
            rows = self.track.get_entries_in_range(date_from, date_to)
        except Exception:
            rows = []

        # Budget-Summen für Progress-Bars
        budget_sums = self._budget_sums_by_typ_for_range(date_from, date_to)

        # ── KPI-Panel ──
        try:
            self.kpi_panel.refresh_kpis(rows, budget_sums)
            self.kpi_panel.refresh_charts(rows, year, month_idx)
        except Exception as e:
            logger.warning("kpi_panel refresh: %s", e)

        # ── Budget-Panel ──
        try:
            self.budget_panel.refresh_budget_overview(year, month_idx, self._cat_caches)
        except Exception as e:
            logger.warning("budget_panel overview: %s", e)

        try:
            typ_filter_display = self.right_panel.typ_combo.currentText()
            self.budget_panel.refresh_tabular(
                date_from, date_to, self._cat_caches, typ_filter_display, range_idx
            )
        except Exception as e:
            logger.warning("budget_panel tabular: %s", e)

        try:
            self.budget_panel.refresh_budget_table(
                date_from, date_to, year, month_idx, range_idx, self.track
            )
        except Exception as e:
            logger.warning("budget_panel table: %s", e)

        # ── Sparziele ──
        try:
            self.savings_panel.refresh()
        except Exception as e:
            logger.warning("savings_panel refresh: %s", e)

        # ── Rechtes Panel (Transaktionen) ──
        try:
            cat_tree = self._build_cat_tree()
            self.right_panel.load(date_from, date_to, cat_tree=cat_tree)
        except Exception as e:
            logger.warning("right_panel load: %s", e)

    def refresh(self) -> None:
        """Kompatibilität: MainWindow ruft refresh() beim Tab-Wechsel."""
        self.refresh_data()

    # ── Kategorie-Caches ─────────────────────────────────────────────────────

    def _load_categories(self) -> None:
        cats = self.categories.get_all_categories()
        name_to_id: dict[tuple[str, str], int] = {}
        id_to_name_typ: dict[int, tuple[str, str]] = {}
        children: dict[int, list[int]] = {}
        parent: dict[int, int | None] = {}

        for c in cats:
            cid = int(c["id"])
            typ = str(c.get("typ") or "")
            name = str(c.get("name") or "")
            pid = c.get("parent_id")
            pid = int(pid) if pid is not None else None

            parent[cid] = pid
            name_to_id[(typ, name)] = cid
            id_to_name_typ[cid] = (typ, name)
            children.setdefault(cid, [])
            if pid is not None:
                children.setdefault(pid, []).append(cid)

        self._cat_caches = {
            "name_to_id":   name_to_id,
            "id_to_name_typ": id_to_name_typ,
            "children":     children,
            "parent":       parent,
            "all":          cats,
        }
        self._descendant_name_cache = {}

        # Kategorie-Combo im rechten Panel aktualisieren
        self.right_panel.update_categories(tr("lbl.all"), [c["name"] for c in cats])

    def _load_tags(self) -> None:
        tags = self.tags.get_all_tags()
        tag_map = {tag["name"]: tag["id"] for tag in tags}
        self._tag_name_to_id = tag_map
        self.right_panel.update_tags(tag_map)

    def _build_cat_tree(self) -> dict:
        """Baut einen Dict {(typ, cat_name): set_of_all_descendants} für Hierarchie-Filter."""
        tree = {}
        id_to_name_typ = self._cat_caches.get("id_to_name_typ", {})
        children = self._cat_caches.get("children", {})

        def _descendants(cid: int) -> set[str]:
            key = id_to_name_typ.get(cid, ("", ""))
            result = {key[1]} if key[1] else set()
            for ch in children.get(cid, []):
                result |= _descendants(int(ch))
            return result

        for cid, (typ, name) in id_to_name_typ.items():
            if name:
                desc = _descendants(cid)
                tree[(typ, name)] = desc
        return tree

    def _get_descendant_names(self, typ: str, selected_name: str) -> set[str]:
        key = (typ, selected_name)
        if key in self._descendant_name_cache:
            return self._descendant_name_cache[key]
        name_to_id = self._cat_caches.get("name_to_id", {})
        children = self._cat_caches.get("children", {})
        id_to_name_typ = self._cat_caches.get("id_to_name_typ", {})

        cid = name_to_id.get(key)
        if cid is None:
            return set()

        result: set[str] = set()

        def _collect(c: int) -> None:
            _, n = id_to_name_typ.get(c, ("", ""))
            if n:
                result.add(n)
            for ch in children.get(c, []):
                _collect(int(ch))

        _collect(cid)
        self._descendant_name_cache[key] = result
        return result

    def _budget_sums_by_typ_for_range(self, date_from: date, date_to: date) -> dict[str, float]:
        months = _months_between(date_from, date_to)
        out = {TYP_INCOME: 0.0, TYP_EXPENSES: 0.0, TYP_SAVINGS: 0.0}
        try:
            raw = self.budget.sum_by_typ_range(months)
            for typ, val in raw.items():
                t = _norm_typ(typ)
                out[t] = out.get(t, 0.0) + val
        except Exception as e:
            logger.debug("budget_sums_by_typ: %s", e)
        return out

    # ── Interaktion ──────────────────────────────────────────────────────────

    def _on_kpi_clicked(self, typ: str) -> None:
        """KPI-Card Klick: Typ-Filter setzen + Transaktionen-Tab öffnen."""
        typ_norm = normalize_typ(typ)
        self.right_panel.set_typ(typ_norm if typ_norm in (TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS) else tr("lbl.all"))
        self.refresh_data()

    def _on_chart_category_clicked(self, category_name: str) -> None:
        if not category_name:
            return
        self.right_panel.set_typ(TYP_EXPENSES)
        idx = self.right_panel.category_combo.findText(category_name)
        if idx >= 0:
            self.right_panel.category_combo.setCurrentIndex(idx)
        self.refresh_data()

    def _on_chart_type_clicked(self, typ_name: str) -> None:
        if not typ_name:
            return
        self._on_kpi_clicked(typ_name)

    def _on_maincat_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        try:
            if not item:
                return
            cid = item.data(0, Qt.UserRole)
            if cid is None:
                return
            typ, name = self._cat_caches.get("id_to_name_typ", {}).get(int(cid), ("", ""))
            if not name:
                return
            if typ:
                self.right_panel.set_typ(display_typ(typ))
            idx = self.right_panel.category_combo.findText(name)
            if idx >= 0:
                self.right_panel.category_combo.setCurrentIndex(idx)
            self.refresh_data()
        except Exception as e:
            logger.debug("_on_maincat_item_double_clicked: %s", e)

    def _on_budget_cell_double_clicked(self, row: int, col: int) -> None:
        try:
            months = self.budget_panel._budget_table_months
            if not months or col < 0 or col >= len(months):
                return
            y, m = months[col]
            row_labels = [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]
            if row < 0 or row >= len(row_labels):
                return
            typ = row_labels[row]

            with QSignalBlocker(self.range_combo):
                self.range_combo.setCurrentIndex(0)
            y_txt = str(int(y))
            y_idx = self.year_combo.findText(y_txt)
            if y_idx < 0:
                self.year_combo.addItem(y_txt)
                y_idx = self.year_combo.findText(y_txt)
            self.year_combo.setCurrentIndex(y_idx)
            if 1 <= int(m) <= 12:
                self.month_combo.setCurrentIndex(int(m))
            self.budget_panel.month_window_combo.setCurrentIndex(0)

            self.right_panel.set_typ(typ)
            self.refresh_data()
        except Exception as e:
            logger.debug("_on_budget_cell_double_clicked: %s", e)

    def _on_budget_overview_edit_requested(self, typ: str, category: str) -> None:
        try:
            if not typ or not category:
                return
            try:
                year = int(self.year_combo.currentText())
            except (ValueError, AttributeError):
                year = date.today().year
            month_idx = self.month_combo.currentIndex()
            month = month_idx if month_idx > 0 else (date.today().month if year == date.today().year else 1)
            self.budget_edit_requested.emit(typ, category, year, month)
        except Exception as e:
            logger.debug("_on_budget_overview_edit_requested: %s", e)

    def _show_budget_suggestions_dialog(self) -> None:
        try:
            year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            year = date.today().year
        month_idx = self.month_combo.currentIndex()
        # Gleiche Logik wie im Banner: Vorjahr → Monat 12, aktuelles Jahr → heute
        if month_idx == 0:
            current_month = date.today().month if year == date.today().year else 12
        else:
            current_month = month_idx

        try:
            from model.budget_warnings_model_extended import BudgetWarningsModelExtended
            from views.budget_adjustment_dialog import BudgetAdjustmentDialog
            warnings_model = BudgetWarningsModelExtended(self.conn)
            min_months = int(self.settings.get("budget_suggestion_months", 3) or 3)
            exceedances = warnings_model.check_warnings_extended(
                year, current_month, lookback_months=min_months
            )
            if not exceedances:
                QMessageBox.information(
                    self, tr("msg.budget_suggestions"),
                    trf("overview.no_suggestions", year=year, month=f"{current_month:02d}")
                )
                return
            budget_model = BudgetModel(self.conn)
            dlg = BudgetAdjustmentDialog(self, warnings_model, budget_model, year, current_month)
            dlg.exec()
        except Exception as e:
            logger.warning("_show_budget_suggestions_dialog: %s", e)

    def _show_overrun_details(self, overruns: list[dict]) -> None:
        if not overruns:
            return
        overruns_sorted = sorted(overruns, key=lambda o: float(o.get("rest", 0.0) or 0.0))
        lines = []
        for o in overruns_sorted[:40]:
            typ  = str(o.get("typ", ""))
            name = str(o.get("category", ""))
            b    = float(o.get("budget", 0.0) or 0.0)
            a    = float(o.get("actual", 0.0) or 0.0)
            rest = float(o.get("rest", 0.0) or 0.0)
            pct  = o.get("pct")
            pct_txt = "—" if pct is None else f"{float(pct):.0f}%"
            status = tr("overview.status_goal_not_reached") if typ == TYP_INCOME else tr("overview.status_budget_exceeded")
            lines.append(
                trf("overview.overrun_line",
                    typ=typ, name=name, budget=format_chf(b), actual=format_chf(a),
                    rest=format_chf(rest), pct=pct_txt, status=status)
            )
        if len(overruns_sorted) > 40:
            lines.append(trf("overview.more_items", n=len(overruns_sorted) - 40))

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(tr("dlg.budget_warnings"))
        msg.setText(tr("overview.categories_outside_plan"))
        msg.setInformativeText(
            tr("overview.tip_budget_warnings")
        )
        msg.setDetailedText("\n".join(lines))
        msg.exec()

    def _toggle_right_panel(self) -> None:
        if self._right_panel_visible:
            self._splitter_sizes = self.main_splitter.sizes()
            total = sum(self._splitter_sizes)
            self.main_splitter.setSizes([total, 0])
            self.right_panel.setVisible(False)
            self._right_panel_visible = False
        else:
            self.right_panel.setVisible(True)
            if self._splitter_sizes:
                self.main_splitter.setSizes(self._splitter_sizes)
            self._right_panel_visible = True

    # ── Refresh Lifecycle ────────────────────────────────────────────────────

    def _delayed_refresh(self) -> None:
        self._refresh_timer.stop()
        self._refresh_timer.start(250)

    def _do_guarded_refresh(self) -> None:
        if self._is_visible:
            self.refresh_data()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._is_visible = True

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._is_visible = False
