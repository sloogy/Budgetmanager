from __future__ import annotations

import logging
import os
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
    QComboBox,
    QCheckBox,
)

from model.favorites_model import FavoritesModel
from model.savings_goals_model import SavingsGoalsModel, STATUS_SAVING, STATUS_RELEASED
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.pot_reserve_model import PotReserveModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from model.date_ranges import month_bounds
from model.salary_cycle import SalaryCycle, previous_salary_cycle, resolve_salary_cycle
from utils.i18n import display_typ, tr, trf
from settings import Settings
from utils import cockpit_presets as _cp
from views.cockpit_charts import DonutChart, TrendAreaChart
from views.ui_colors import ui_colors
from utils.cockpit_layout import (
    LAYOUT_AUTO,
    LAYOUT_FIXED,
    arrange_columns,
    columns_from_lists,
    normalize_columns,
    normalize_mode,
    normalize_order,
)
from views.cockpit_sections import (
    CollapsibleSection,
    ResponsiveColumns,
    fit_table_height,
)
from utils.money import format_money
from utils.icons import get_icon

logger = logging.getLogger(__name__)


# Modulweite Cockpit-Layoutvorgaben. Comprehensions in einem Klassenkörper
# besitzen einen eigenen Scope und dürfen deshalb nicht auf zuvor definierte
# Klassenattribute zugreifen.
_COCKPIT_LEFT_COLUMN_PANELS = ("kpis", "quick_actions")
_COCKPIT_DEFAULT_PANEL_COLUMNS = {
    key: ("left" if key in _COCKPIT_LEFT_COLUMN_PANELS else "right")
    for key in _cp.PANEL_KEYS
}


class _Card(QFrame):
    def __init__(
        self,
        title: str,
        value: str = "",
        hint: str = "",
        *,
        icon: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("cockpitCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.lbl_icon = QLabel(icon, self)
        self.lbl_icon.setObjectName("cockpitCardIcon")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setFixedSize(30, 30)
        top.addWidget(self.lbl_icon)
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setObjectName("cockpitCardLabel")
        self.lbl_title.setWordWrap(True)
        top.addWidget(self.lbl_title, 1)
        lay.addLayout(top)

        self.lbl_value = QLabel(value, self)
        self.lbl_value.setObjectName("cockpitCardValue")
        self.lbl_value.setWordWrap(True)
        lay.addWidget(self.lbl_value)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        # Beide Labels immer einhängen: ein später sichtbar gemachtes,
        # parentloses QLabel würde von Qt als eigenes Fenster behandelt.
        self.lbl_hint = QLabel(hint, self)
        self.lbl_hint.setObjectName("cockpitCardCaption")
        self.lbl_hint.setWordWrap(True)
        bottom.addWidget(self.lbl_hint, 1)
        self.lbl_trend = QLabel("", self)
        self.lbl_trend.setObjectName("cockpitCardTrend")
        self.lbl_trend.setVisible(False)
        bottom.addWidget(self.lbl_trend)
        lay.addLayout(bottom)
        self.lbl_hint.setVisible(bool(hint))

    def set_trend(self, delta: float, colors, *, higher_is_better: bool = True) -> None:
        """Zeigt den Vergleich zum Vormonat mit Farben des aktiven Profils."""
        if not delta:
            self.lbl_trend.setVisible(False)
            return
        rising = delta > 0
        good = rising if higher_is_better else not rising
        arrow = "\u2197" if rising else "\u2198"
        # Keine feste/inline Farbe: der ThemeManager wertet diese Property
        # gegen das aktive Designprofil aus. ``colors`` bleibt Teil der API,
        # damit die fachliche Herkunft explizit und rückwärtskompatibel ist.
        _ = colors
        self.lbl_trend.setProperty("trendState", "good" if good else "bad")
        self.lbl_trend.setText(f"{arrow} {abs(delta):,.0f}".replace(",", "'"))
        style = self.lbl_trend.style()
        style.unpolish(self.lbl_trend)
        style.polish(self.lbl_trend)
        self.lbl_trend.setVisible(True)

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
    layout_mode_changed = Signal(bool)  # True = fixed/manual drag-and-drop

    PANEL_DEFAULTS = {key: True for key in _cp.PANEL_KEYS}

    PANEL_TITLE_KEYS = {
        "kpis": "cockpit.panel.kpis",
        "quick_actions": "cockpit.panel.quick_actions",
        "action_needed": "cockpit.panel.action_needed",
        "charts": "cockpit.panel.charts",
        "favorites": "cockpit.panel.favorites",
        "savings": "cockpit.panel.savings",
        "recent": "cockpit.panel.recent",
    }
    PANEL_ORDER_DEFAULTS = list(_cp.PANEL_KEYS)

    # ADHS-freundliche Voreinstellungen: ein klarer Start statt acht gleich
    # gewichteter Bereiche. Individuelle Anpassung bleibt weiterhin möglich.
    # v2.2.22: EINE Wahrheit fuer Presets – utils/cockpit_presets.py
    COCKPIT_PRESETS = _cp.PRESETS

    def __init__(self, conn: sqlite3.Connection, settings: Settings | None = None):
        super().__init__()
        self.conn = conn
        self.settings = settings or Settings()
        _cp.materialize_initial(self.settings)
        self._ensure_budget_warnings_panel_visible()
        self._warnings_model_ext = None  # lazy: BudgetWarningsModelExtended
        self._panel_widgets: dict[str, QWidget] = {}
        self._setup_ui()
        self.refresh()

    def _ensure_budget_warnings_panel_visible(self) -> None:
        """Budgetwarnungen im Cockpit sichtbar halten (Alt-Migration).

        v2.2.22 (UI/ADHS-Audit): delegiert an utils/cockpit_presets.
        Vorher lief die Migration bedingungslos im Konstruktor und
        materialisierte die ALL-TRUE-Defaults – dadurch wirkte das
        Fokus-Preset bei Neuinstallationen nie (Marker
        cockpit_warnings_visible_migrated_v2014 blieb als Kennung erhalten).
        """
        _cp.migrate_v2014(self.settings)

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
        title.setObjectName("cockpitTitle")
        subtitle = QLabel(tr("cockpit.subtitle"))
        subtitle.setObjectName("cockpitSubtitle")
        title_box = QVBoxLayout()
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.preset_combo = QComboBox()
        self.preset_combo.setToolTip(tr("cockpit.preset_tip"))
        self.preset_combo.setAccessibleName(tr("cockpit.preset_accessible"))
        self.preset_combo.addItem(tr("cockpit.preset_focus"), "focus")
        self.preset_combo.addItem(tr("cockpit.preset_standard"), "standard")
        self.preset_combo.addItem(tr("cockpit.preset_analysis"), "analysis")
        self.preset_combo.addItem(tr("cockpit.preset_custom"), "custom")
        preset = str(self.settings.get("cockpit_preset", "focus") or "focus")
        preset_index = self.preset_combo.findData(preset)
        self.preset_combo.setCurrentIndex(max(0, preset_index))
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        header.addWidget(self.preset_combo)

        self.btn_customize = QPushButton(tr("cockpit.customize"))
        self.btn_customize.setToolTip(tr("cockpit.customize_tip"))
        self.btn_customize.clicked.connect(self._show_customize_menu)
        header.addWidget(self.btn_customize)
        self.btn_fix_tiles = QPushButton(tr("cockpit.fix_tiles"))
        self.btn_fix_tiles.setCheckable(True)
        self.btn_fix_tiles.setToolTip(tr("cockpit.fix_tiles_tip"))
        self.btn_fix_tiles.setChecked(self.is_layout_fixed())
        self.btn_fix_tiles.toggled.connect(self.set_layout_fixed)
        header.addWidget(self.btn_fix_tiles)
        self.btn_month_close = QPushButton(tr("cockpit.month_close"))
        self.btn_month_close.setToolTip(tr("help.month_close"))
        self.btn_month_close.clicked.connect(self._open_month_close)
        header.addWidget(self.btn_month_close)
        self.btn_refresh = QPushButton(tr("cockpit.refresh"))
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        self.body_layout.addLayout(header)

        # v2.2.0: Ampel-Monatsstatus – eine Zeile, sofort verständlich.
        self.lbl_month_status = QLabel("")
        self.lbl_month_status.setObjectName("cockpitMonthStatus")
        self.lbl_month_status.setToolTip(tr("status.month_tooltip"))
        self.body_layout.addWidget(self.lbl_month_status)

        # v2.2.3 (Führung): dynamische "Nächste Schritte" – beantwortet
        # DIE Einsteigerfrage "Und was mache ich jetzt?" mit max. 3 konkreten,
        # aus den echten Daten abgeleiteten Handlungen.
        self.lbl_next_steps = QLabel("")
        self.lbl_next_steps.setObjectName("cockpitNextSteps")
        self.lbl_next_steps.setWordWrap(True)
        self.body_layout.addWidget(self.lbl_next_steps)

        # v2.2.40: Abschnitte liegen in ein bis zwei Spalten (je nach Breite)
        # und sind einzeln auf-/zuklappbar. Der Zustand wird gespeichert.
        self.columns = ResponsiveColumns()
        self.columns.layout_changed.connect(self._on_columns_reordered)
        self.body_layout.addWidget(self.columns)
        self._sections: dict[str, CollapsibleSection] = {}

        # KPIs
        self.kpi_panel = QWidget()
        kpi_lay = QGridLayout(self.kpi_panel)
        kpi_lay.setContentsMargins(0, 0, 0, 0)
        # Unicode-Symbole statt Emoji: stabil unter Fedora/GNOME ohne Emoji-Font.
        self.card_income = _Card(display_typ(TYP_INCOME), "–", icon="\u2191")
        self.card_expenses = _Card(display_typ(TYP_EXPENSES), "–", icon="\u2193")
        self.card_savings = _Card(display_typ(TYP_SAVINGS), "–", icon="\u25c6")
        self.card_balance = _Card(tr("cockpit.free_amount"), "–", icon="\u2211")
        self.card_balance.setToolTip(tr("month_close.free_amount_tip"))
        self.card_savings.setToolTip(tr("help.savings"))
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

        # Diagramme: Ring nach Ausgabenkategorie und kumulierter Monatsverlauf.
        self.charts_panel = QWidget()
        charts_lay = QHBoxLayout(self.charts_panel)
        charts_lay.setContentsMargins(0, 0, 0, 0)
        charts_lay.setSpacing(12)
        self.chart_donut = DonutChart()
        self.chart_trend = TrendAreaChart()
        charts_lay.addWidget(self.chart_donut, 4)
        charts_lay.addWidget(self.chart_trend, 6)
        self._add_panel("charts", self.charts_panel)

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

        # v2.2.40: Warnungen, Budget-Ampel und fehlende Buchungen beantworten
        # dieselbe Frage – sie bilden einen Abschnitt mit drei Blöcken. Leere
        # Blöcke verschwinden, der Zähler in der Kopfzeile nennt die Summe.
        self.action_needed_panel = QWidget()
        action_lay = QVBoxLayout(self.action_needed_panel)
        action_lay.setContentsMargins(0, 0, 0, 0)
        action_lay.setSpacing(10)

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
        action_lay.addWidget(self.warnings_panel)

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
        action_lay.addWidget(self.budget_warnings_panel)

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
        action_lay.addWidget(self.missing_panel)
        self._add_panel("action_needed", self.action_needed_panel)

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

    def _open_month_close(self) -> None:
        """Öffnet den Monatsabschluss-Assistenten.

        Vormonate haben Vorrang: wenn z. B. Juni noch offen ist und heute
        bereits Juli ist, öffnet der Button Juni statt stumpf den laufenden
        Monat. Das hält Monatsabschluss, Carryover und Vorschläge chronologisch
        sauber.
        """
        try:
            from datetime import date as _date

            from model.month_close_model import MonthCloseModel
            from views.month_close_dialog import MonthCloseDialog

            today = _date.today()
            suggested = MonthCloseModel(self.conn).suggested_month_to_close(today)
            target_year, target_month = suggested or (today.year, today.month)
            dlg = MonthCloseDialog(self.conn, target_year, target_month, self)
            dlg.exec()
            self.refresh()
        except Exception as e:
            logger.warning("month close dialog: %s", e)

    def _section(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl = QLabel(title, frame)
        lbl.setObjectName("cockpitInnerTitle")
        lbl.move(10, 6)
        return frame

    def _table_section(self, title: str, headers: list[str]) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 10)
        lbl = QLabel(title)
        lbl.setObjectName("cockpitInnerTitle")
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        table.setWordWrap(False)
        table.setMinimumWidth(640)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(QHeaderView.Interactive)
        lay.addWidget(lbl)
        lay.addWidget(table)
        return frame

    #: Kennzahlen und Aktionen links, Listen rechts – nur bei breitem Fenster.
    LEFT_COLUMN_PANELS = _COCKPIT_LEFT_COLUMN_PANELS
    DEFAULT_PANEL_COLUMNS = dict(_COCKPIT_DEFAULT_PANEL_COLUMNS)

    def _add_panel(self, key: str, widget: QWidget) -> None:
        """Hängt ein Panel als aufklappbaren Abschnitt in die passende Spalte."""
        section = CollapsibleSection(key, self._panel_title(key))
        section.add_widget(widget)
        section.set_collapsed(self._is_collapsed(key), notify=False)
        section.toggled.connect(self._on_section_toggled)
        self._sections[key] = section
        self._panel_widgets[key] = section
        column = "left" if key in self.LEFT_COLUMN_PANELS else "right"
        self.columns.add(section, column=column)

    # ── Auf-/Zuklappen ──────────────────────────────────────────
    #: Beim ersten Start offen: alles Übrige klappt der Nutzer selbst auf.
    DEFAULT_OPEN_PANELS = ("kpis", "action_needed", "savings")

    def _collapsed_config(self) -> dict[str, bool]:
        cfg = self.settings.get("cockpit_collapsed_sections", None)
        return dict(cfg) if isinstance(cfg, dict) else {}

    def _is_collapsed(self, key: str) -> bool:
        cfg = self._collapsed_config()
        if key in cfg:
            return bool(cfg[key])
        return key not in self.DEFAULT_OPEN_PANELS

    def _on_section_toggled(self, key: str, collapsed: bool) -> None:
        cfg = self._collapsed_config()
        cfg[key] = bool(collapsed)
        try:
            self.settings.set("cockpit_collapsed_sections", cfg)
        except Exception as exc:  # pragma: no cover
            logger.debug("Abschnittszustand nicht speicherbar: %s", exc)

    def _update_section_state(self, key: str, count: int, hint_key: str) -> None:
        """Zähler setzen und leere Abschnitte auf eine Hinweiszeile schrumpfen."""
        section = self._sections.get(key)
        if section is None:
            return
        section.set_count(count)
        section.set_empty(count == 0, tr(hint_key))

    # ── Public API ───────────────────────────────────────────────
    def _panel_title(self, key: str) -> str:
        return tr(self.PANEL_TITLE_KEYS.get(key, key))

    def get_panel_specs(self) -> list[tuple[str, str]]:
        return [(k, self._panel_title(k)) for k in self._panel_order()]

    def set_panel_visible(self, key: str, visible: bool) -> None:
        _cp.set_panel(self.settings, key, visible)
        self._apply_panel_visibility()

    def _on_preset_changed(self, _index: int) -> None:
        preset = str(self.preset_combo.currentData() or "focus")
        _cp.apply_preset(self.settings, preset)
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
        self._refresh_charts(y, m)
        self._refresh_next_steps(y, m)
        self._refresh_section_states()
        self._apply_panel_visibility()

    def _refresh_section_states(self) -> None:
        """Zähler und Leerzustände aller Abschnitte nachziehen.

        Der Zähler für „Handlungsbedarf" ist die Summe aus Warnungen,
        Budget-Ampel und fehlenden Buchungen – die drei Blöcke stehen seit
        v2.2.40 in einem Abschnitt.
        """
        try:
            action_rows = sum(
                table.rowCount()
                for table in (
                    self.tbl_warnings,
                    self.tbl_budget_warnings,
                    self.tbl_missing,
                )
            )
            for panel, table in (
                (self.warnings_panel, self.tbl_warnings),
                (self.budget_warnings_panel, self.tbl_budget_warnings),
                (self.missing_panel, self.tbl_missing),
            ):
                panel.setVisible(table.rowCount() > 0)
            self._update_section_state(
                "action_needed", action_rows, "cockpit.empty_action_needed"
            )
            self._update_section_state(
                "charts",
                int(getattr(self, "_charts_count", 0) or 0),
                "cockpit.empty_charts",
            )
            self._update_section_state(
                "favorites", self.tbl_favorites.rowCount(), "cockpit.empty_favorites"
            )
            self._update_section_state(
                "recent", self.tbl_recent.rowCount(), "cockpit.empty_recent"
            )
            goals = int(getattr(self, "_active_savings_count", 0) or 0)
            self._update_section_state("savings", goals, "cockpit.empty_savings")
            # Automatikmodus: leere, kompakt geschrumpfte Kacheln nach unten.
            # Fixierter Modus behält dagegen exakt die vom Nutzer gewählte Position.
            self._apply_panel_order()
        except Exception as exc:  # pragma: no cover - Anzeige darf nie stoppen
            logger.debug("Abschnittszustände nicht aktualisierbar: %s", exc)

    def _refresh_next_steps(self, y: int, m: int) -> None:
        """v2.2.3 (Führung): bis zu 3 konkrete nächste Handlungen ableiten."""
        steps: list[str] = []
        try:
            start, end = month_bounds(y, m)
            n_book = int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM tracking WHERE date >= ? AND date < ?",
                    (start, end),
                ).fetchone()[0]
            )
            if n_book == 0:
                # Empty State: klarer Startpunkt statt leerer Flächen.
                steps.append(tr("cockpit.next_first_booking"))

            n_missing = int(getattr(self, "_missing_count", 0) or 0)
            if n_missing > 0:
                steps.append(trf("cockpit.next_missing_fix", n=n_missing))

            from datetime import date as _date

            from model.month_close_model import MonthCloseModel

            today = _date.today()
            month_close_model = MonthCloseModel(self.conn)
            open_past_months = month_close_model.list_open_months_before(y, m, limit=12)
            if open_past_months:
                oy, om = open_past_months[0]
                steps.append(
                    trf(
                        "cockpit.next_past_month_close",
                        month=tr(f"month.{om}"),
                        year=oy,
                        n_more=max(0, len(open_past_months) - 1),
                    )
                )
            elif today.day >= 25 and not month_close_model.is_closed(y, m):
                steps.append(tr("cockpit.next_month_close"))
        except Exception as e:
            logger.debug("next steps: %s", e)

        if not steps:
            self.lbl_next_steps.setText(tr("cockpit.next_all_good"))
        else:
            self.lbl_next_steps.setText(
                tr("cockpit.next_steps_title") + " " + "  ·  ".join(steps[:3])
            )

    # ── Refresh helpers ──────────────────────────────────────────
    def _sum_budget_actual(
        self,
        y: int,
        m: int,
        typ: str,
        category: str | None = None,
        *,
        actual_start: str | None = None,
        actual_end: str | None = None,
    ) -> tuple[float, float]:
        """Liest Monatsbudget und Ist-Wert eines frei wählbaren Zeitraums.

        Das Budget bleibt einem Kalendermonat zugeordnet. Der Cockpit-
        Monatsstatus kann den Ist-Wert dagegen zwischen zwei Lohnterminen
        berechnen. Ohne Grenzen bleibt das bisherige Kalendermonatsverhalten.
        """
        if actual_start is None or actual_end is None:
            actual_start, actual_end = month_bounds(y, m)
        params_b: list[object] = [y, m, typ]
        params_a: list[object] = [actual_start, actual_end, typ]
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

    @staticmethod
    def _cycle_period_text(cycle: SalaryCycle) -> str:
        start = cycle.start.strftime("%d.%m.%Y")
        end = cycle.end_inclusive.strftime("%d.%m.%Y")
        if cycle.category:
            return trf(
                "status.salary_cycle_period",
                category=cycle.category,
                start=start,
                end=end,
            )
        return trf("status.calendar_period", start=start, end=end)

    def _refresh_kpis(self, y: int, m: int) -> None:
        # v2.2.57: Der Cockpit-Monatsstatus folgt dem Lohnzyklus statt starr
        # dem 1.–Monatsende. Ohne erkennbare Lohnkategorie bleibt der
        # Kalendermonat als sicherer Fallback erhalten.
        cycle = resolve_salary_cycle(self.conn, on_date=date.today())
        budget_y, budget_m = cycle.budget_year, cycle.budget_month
        bounds = {"actual_start": cycle.start_iso, "actual_end": cycle.end_iso}
        income_b, income_a = self._sum_budget_actual(
            budget_y, budget_m, TYP_INCOME, **bounds
        )
        exp_b, exp_a = self._sum_budget_actual(
            budget_y, budget_m, TYP_EXPENSES, **bounds
        )
        sav_b, sav_a = self._sum_budget_actual(
            budget_y, budget_m, TYP_SAVINGS, **bounds
        )
        budget_hint = trf(
            "cockpit.kpi_budget_cycle",
            amount="{amount}",
            month=tr(f"month.{budget_m}"),
            year=budget_y,
        )
        self.card_income.set_values(
            format_money(income_a),
            budget_hint.format(amount=format_money(income_b)),
        )
        self.card_expenses.set_values(
            format_money(exp_a),
            budget_hint.format(amount=format_money(exp_b)),
        )
        self.card_savings.set_values(
            format_money(sav_a),
            budget_hint.format(amount=format_money(sav_b)),
        )
        rest = income_a - exp_a - sav_a
        hint = (
            tr("cockpit.balance_positive")
            if rest >= 0
            else tr("cockpit.balance_warning")
        )
        self.card_balance.set_values(format_money(rest), hint)
        self._refresh_kpi_trends(cycle, income_a, exp_a, sav_a, rest)

        try:
            from model.month_status import compute_month_status

            st = compute_month_status(income_a, exp_a, exp_b, sav_a)
            period = self._cycle_period_text(cycle)
            self.lbl_month_status.setText(
                f"{st.icon} {tr(st.text_key)} · {period} – "
                f"{tr('cockpit.free_amount')}: {format_money(st.free_amount)}"
            )
            self.lbl_month_status.setToolTip(
                trf(
                    "status.salary_cycle_tooltip",
                    period=period,
                    budget_month=tr(f"month.{budget_m}"),
                    budget_year=budget_y,
                )
            )
        except Exception as e:
            logger.debug("month status: %s", e)

    def _refresh_charts(self, y: int, m: int) -> None:
        """Füllt Ring und Flächenverlauf aus den Buchungen des Monats."""
        disabled = os.getenv("BM_DISABLE_COCKPIT_CHARTS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.chart_donut.setVisible(not disabled)
        self.chart_trend.setVisible(not disabled)
        if disabled:
            self._charts_count = 0
            logger.info(
                "Cockpit-Diagramme durch BM_DISABLE_COCKPIT_CHARTS deaktiviert."
            )
            return

        try:
            start, end = month_bounds(y, m)
            rows = self.conn.execute(
                "SELECT category, COALESCE(SUM(amount),0) FROM tracking "
                "WHERE typ=? AND date>=? AND date<? GROUP BY category",
                (TYP_EXPENSES, start, end),
            ).fetchall()
            items = [(str(cat), float(total or 0)) for cat, total in rows]
            total = sum(value for _, value in items)
            self._charts_count = sum(1 for _, value in items if value > 0)
            self.chart_donut.set_data(items, format_money(total))

            daily = self.conn.execute(
                "SELECT date, COALESCE(SUM(amount),0) FROM tracking "
                "WHERE typ=? AND date>=? AND date<? GROUP BY date ORDER BY date",
                (TYP_EXPENSES, start, end),
            ).fetchall()
            running, series = 0.0, []
            for _, amount in daily:
                running += float(amount or 0)
                series.append(running)
            self.chart_trend.set_data(series)
        except Exception as exc:  # pragma: no cover - Diagramm ist Beiwerk
            self._charts_count = 0
            logger.debug("Cockpit-Diagramme nicht aktualisierbar: %s", exc)

    def _refresh_kpi_trends(
        self,
        cycle: SalaryCycle,
        income_a: float,
        exp_a: float,
        sav_a: float,
        rest: float,
    ) -> None:
        """Vergleicht die Kennzahlen mit dem vorherigen Lohnzyklus."""
        try:
            colors = ui_colors(self)
            previous = previous_salary_cycle(cycle)
            bounds = {
                "actual_start": previous.start_iso,
                "actual_end": previous.end_iso,
            }
            _, prev_income = self._sum_budget_actual(
                previous.budget_year, previous.budget_month, TYP_INCOME, **bounds
            )
            _, prev_exp = self._sum_budget_actual(
                previous.budget_year, previous.budget_month, TYP_EXPENSES, **bounds
            )
            _, prev_sav = self._sum_budget_actual(
                previous.budget_year, previous.budget_month, TYP_SAVINGS, **bounds
            )
            prev_rest = prev_income - prev_exp - prev_sav
            self.card_income.set_trend(income_a - prev_income, colors)
            self.card_expenses.set_trend(
                exp_a - prev_exp, colors, higher_is_better=False
            )
            self.card_savings.set_trend(sav_a - prev_sav, colors)
            self.card_balance.set_trend(rest - prev_rest, colors)
        except Exception as exc:  # pragma: no cover - Trend ist Beiwerk
            logger.debug("KPI-Trend nicht berechenbar: %s", exc)

    def _set_table_rows(
        self, table: QTableWidget, rows: Iterable[Iterable[str]], empty_text: str
    ) -> None:
        rows = list(rows)
        # v2.2.40: Leere Tabellen bekommen keine Platzhalterzeile mehr. Der
        # Hinweis steht jetzt in der Kopfzeile des Abschnitts, die Tabelle
        # selbst wird ausgeblendet – vorher kostete jede leere Liste rund
        # 150 px Mindesthöhe plus Rahmen.
        if not rows:
            table.setRowCount(0)
            table.setVisible(False)
            table.setToolTip(empty_text)
            self._stabilize_table_columns(table)
            fit_table_height(table)
            return
        table.setVisible(True)
        table.setToolTip("")
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(r, c, item)
        self._stabilize_table_columns(table)
        fit_table_height(table)

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
        pot_model = PotReserveModel(self.conn)
        try:
            co_start = int(self.settings.get("carryover_start_month", 1) or 1)
            co_year_raw = int(self.settings.get("carryover_start_year", 0) or 0)
            co_year = co_year_raw if co_year_raw > 0 else y
        except Exception:
            co_start, co_year = 1, y
        for typ, cat in favs:
            pot = pot_model.status(
                y, m, typ, cat, start_month=co_start, start_year=co_year
            )
            if pot is not None:
                rows.append(
                    [
                        display_typ(typ),
                        cat,
                        format_money(pot.cap),
                        format_money(pot.spent),
                        format_money(pot.rest),
                    ]
                )
                continue
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
        # Der Layout-Zähler ist kein verlässlicher Sparziel-Zähler: Jede
        # Zielzeile ist ein QHBoxLayout und es gibt kein festes Titel-Element.
        # Das frühere ``count() - 1`` machte daher aus genau einem Ziel den
        # Wert 0 und markierte die komplette Kachel fälschlich als leer.
        self._active_savings_count = len(goals)
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
            contributed = float(getattr(g, "contributed_amount", g.current_amount) or 0)
            used = float(getattr(g, "withdrawn_amount", 0) or 0)
            stock = float(getattr(g, "current_stock", g.current_amount) or 0)
            remaining = float(getattr(g, "remaining_contribution", 0) or 0)
            pct = int(
                max(0, min(100, round(float(getattr(g, "progress_percent", 0) or 0))))
            )
            bar.setValue(pct)
            bar.setFormat(
                trf(
                    "cockpit.savings_flow_bar",
                    percent=pct,
                    contributed=format_money(contributed),
                    target=format_money(target),
                )
            )
            bar.setToolTip(
                trf(
                    "cockpit.savings_flow_tip",
                    contributed=format_money(contributed),
                    used=format_money(used),
                    stock=format_money(stock),
                    remaining=format_money(remaining),
                )
            )
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
            try:
                from settings import Settings

                lookback = int(Settings().get("budget_suggestion_months", 3) or 3)
            except Exception:
                lookback = 3
            excs = self._warnings_model_ext.check_warnings_extended(
                y, m, lookback_months=lookback
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
        seen_keys: set[tuple[str, str]] = set()
        for exc in excs[:10]:
            pct = float(getattr(exc, "percent_used", 0.0) or 0.0)
            cnt = int(getattr(exc, "exceed_count", 0) or 0)
            auslastung = f"{pct:.0f}%" + (f" ({cnt}×)" if cnt > 1 else "")
            sug = getattr(exc, "suggestion", None)
            empfehlung = format_money(float(sug)) if sug else "—"
            _typ = str(getattr(exc, "typ", ""))
            _cat = str(getattr(exc, "category", ""))
            seen_keys.add((_typ, _cat))
            rows.append(
                [
                    display_typ(_typ),
                    _cat,
                    format_money(float(getattr(exc, "budget", 0.0) or 0.0)),
                    format_money(float(getattr(exc, "spent", 0.0) or 0.0)),
                    auslastung,
                    empfehlung,
                ]
            )
        # Tracking-only/Lernmodus und POT-Rückstellungen zusätzlich sichtbar machen.
        # BudgetWarningsModel arbeitet primär schwellenbasiert; Kategorien ohne
        # Budget oder POTs mit Jahres-/Topfrest müssen trotzdem im Cockpit melden.
        if len(rows) < 10:
            try:
                from model.budget_overview_model import BudgetOverviewModel

                overview = BudgetOverviewModel(self.conn)
                learn = overview.get_tracking_budget_suggestions(
                    year=y, current_month=m, show_in_report=True
                )
                for sug in learn:
                    key = (
                        str(getattr(sug, "typ", "")),
                        str(getattr(sug, "category", "")),
                    )
                    if key in seen_keys or not key[1]:
                        continue
                    spent = self._year_to_date_spent(y, m, key[0], key[1])
                    rows.append(
                        [
                            display_typ(key[0]),
                            key[1],
                            format_money(0.0),
                            format_money(spent),
                            tr("cockpit.learning_suggestion"),
                            format_money(
                                float(getattr(sug, "suggested_amount", 0.0) or 0.0)
                            ),
                        ]
                    )
                    seen_keys.add(key)
                    if len(rows) >= 10:
                        break
            except Exception as exc:
                logger.debug("cockpit learning warnings: %s", exc)

        if len(rows) < 10:
            try:
                pot_model = PotReserveModel(self.conn)
                try:
                    co_start = int(self.settings.get("carryover_start_month", 1) or 1)
                    co_year_raw = int(self.settings.get("carryover_start_year", 0) or 0)
                    co_year = co_year_raw if co_year_raw > 0 else y
                except Exception:
                    co_start, co_year = 1, y
                cats = self.conn.execute(
                    "SELECT typ, name FROM categories WHERE typ=? ORDER BY name",
                    (TYP_EXPENSES,),
                ).fetchall()
                for typ, cat in cats:
                    key = (str(typ), str(cat))
                    if key in seen_keys:
                        continue
                    st = pot_model.status(
                        y, m, key[0], key[1], start_month=co_start, start_year=co_year
                    )
                    if st is None:
                        continue
                    if not (st.is_overdrawn or (not st.has_budget and st.spent > 0.01)):
                        continue
                    rows.append(
                        [
                            display_typ(key[0]),
                            key[1],
                            format_money(st.cap),
                            format_money(st.spent),
                            (
                                tr("cockpit.pot_overdrawn")
                                if st.has_budget
                                else tr("cockpit.budget_missing")
                            ),
                            tr("cockpit.set_budget"),
                        ]
                    )
                    seen_keys.add(key)
                    if len(rows) >= 10:
                        break
            except Exception as exc:
                logger.debug("cockpit pot warnings: %s", exc)

        self._set_table_rows(
            self.tbl_budget_warnings, rows, tr("cockpit.empty_budget_warnings")
        )

    def _year_to_date_spent(self, y: int, m: int, typ: str, category: str) -> float:
        """Summe Jan..Monat für Cockpit-Hinweise ohne Budget."""
        try:
            last_day = __import__("calendar").monthrange(int(y), int(m))[1]
            start = f"{int(y):04d}-01-01"
            end = f"{int(y):04d}-{int(m):02d}-{last_day:02d}"
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM tracking WHERE typ=? AND category=? AND date>=? AND date<=?",
                (typ, category, start, end),
            ).fetchone()
            val = float(row[0] if row and row[0] is not None else 0.0)
            return abs(val) if typ != TYP_INCOME else val
        except Exception:
            return 0.0

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
        open_count = 0
        # v2.2.4 (Führung/Stabilität): Fälligkeit je Position berücksichtigen –
        # im laufenden Monat gilt eine Position erst ab ihrem Soll-Tag als
        # offen (siehe model/fixed_cost_due, dort regressionsgesichert).
        from model.fixed_cost_due import is_open_this_month

        for typ, name, is_fix, is_recurring, day in self.conn.execute(sql).fetchall():
            budget = budgets.get((str(typ), str(name)), 0.0)
            booked = booked_totals.get((str(typ), str(name)), 0.0)
            open_item, rest = is_open_this_month(
                is_fix=bool(is_fix),
                is_recurring=bool(is_recurring),
                budget=budget,
                booked=booked,
                due_day=day,
                year=y,
                month=m,
            )
            if open_item:
                open_count += 1
                if len(rows) < 10:
                    rows.append(
                        [
                            display_typ(typ),
                            name,
                            str(day or 1),
                            format_money(rest),
                            tr("cockpit.doubleclick_book"),
                        ]
                    )
        self._set_table_rows(self.tbl_missing, rows, tr("cockpit.empty_missing"))
        self._missing_count = open_count

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

    # ── Cockpit-Layout: automatisch oder fixiert ────────────────
    def _layout_mode(self) -> str:
        """Liest den Modus inklusive Migration des v2.2.42-Schlüssels."""
        mode = normalize_mode(self.settings.get("cockpit_layout_mode", LAYOUT_AUTO))
        # v2.2.42 verwendete vorübergehend einen booleschen Schlüssel. Ein dort
        # fixiertes Layout darf beim Upgrade nicht unbemerkt gelöst werden.
        if bool(self.settings.get("cockpit_tiles_fixed", False)):
            return LAYOUT_FIXED
        return mode

    def is_layout_fixed(self) -> bool:
        return self._layout_mode() == LAYOUT_FIXED

    def _sync_fix_button(self, fixed: bool) -> None:
        button = getattr(self, "btn_fix_tiles", None)
        if button is None:
            return
        previous = button.blockSignals(True)
        try:
            button.setChecked(bool(fixed))
        finally:
            button.blockSignals(previous)

    def set_layout_fixed(self, fixed: bool) -> None:
        """Schaltet zwischen Automatik und fixiertem Drag-and-drop-Layout."""
        fixed = bool(fixed)
        mode = LAYOUT_FIXED if fixed else LAYOUT_AUTO
        changed = mode != self._layout_mode()
        # Beide Schemata in EINEM Schreibvorgang synchron halten. So entsteht
        # bei Absturz/Stromverlust kein Mischzustand zwischen alter und neuer
        # Layout-Einstellung.
        self.settings.set_many(
            {
                "cockpit_layout_mode": mode,
                "cockpit_tiles_fixed": fixed,
            }
        )
        self._sync_fix_button(fixed)
        self._apply_panel_order()
        if changed:
            self.layout_mode_changed.emit(fixed)

    def reset_layout(self) -> None:
        """Setzt Reihenfolge, Spalten und Modus auf das Produkt-Layout zurück."""
        columns = dict(self.DEFAULT_PANEL_COLUMNS)
        self.settings.set_many(
            {
                "cockpit_panel_order": list(self.PANEL_ORDER_DEFAULTS),
                "cockpit_panel_columns": columns,
                "cockpit_tile_columns": dict(columns),
                "cockpit_layout_mode": LAYOUT_AUTO,
                "cockpit_tiles_fixed": False,
            }
        )
        self._sync_fix_button(False)
        self._apply_panel_order()
        self.layout_mode_changed.emit(False)

    def _panel_order(self) -> list[str]:
        return normalize_order(
            self.PANEL_ORDER_DEFAULTS,
            self.settings.get("cockpit_panel_order", None),
            legacy_map=_cp.LEGACY_PANEL_MAP,
        )

    def _panel_columns(self) -> dict[str, str]:
        # v2.2.42 nannte denselben Wert kurzzeitig cockpit_tile_columns.
        # Legacy-Werte überlagern nur ihre tatsächlich gespeicherten Schlüssel.
        raw = self.settings.get("cockpit_panel_columns", None)
        merged = dict(raw) if isinstance(raw, dict) else {}
        legacy = self.settings.get("cockpit_tile_columns", None)
        if isinstance(legacy, dict):
            merged.update(legacy)
        return normalize_columns(
            self.PANEL_ORDER_DEFAULTS,
            merged,
            default_left=self.LEFT_COLUMN_PANELS,
        )

    def _set_panel_order(self, order: list[str]) -> None:
        clean = normalize_order(
            self.PANEL_ORDER_DEFAULTS, order, legacy_map=_cp.LEGACY_PANEL_MAP
        )
        self.settings.set("cockpit_panel_order", clean)
        self._apply_panel_order()
        self._apply_panel_visibility()

    def _on_columns_reordered(self, left_keys: object, right_keys: object) -> None:
        """Persistiert eine direkte Drag-and-drop-Änderung im fixierten Modus."""
        if not self.is_layout_fixed():
            return
        left = [str(key) for key in (left_keys or []) if key in self.PANEL_DEFAULTS]
        right = [str(key) for key in (right_keys or []) if key in self.PANEL_DEFAULTS]
        order = normalize_order(self.PANEL_ORDER_DEFAULTS, left + right)
        columns = columns_from_lists(self.PANEL_ORDER_DEFAULTS, left, right)
        # Falls ein ausgeblendetes Panel beim DnD nicht in den sichtbaren Listen
        # enthalten war, seine bisherige Spalte erhalten.
        previous = self._panel_columns()
        for key in self.PANEL_ORDER_DEFAULTS:
            columns.setdefault(key, previous.get(key, self.DEFAULT_PANEL_COLUMNS[key]))
        self.settings.set_many(
            {
                "cockpit_panel_order": order,
                "cockpit_panel_columns": columns,
                "cockpit_tile_columns": dict(columns),
            }
        )
        self._apply_panel_order()

    def _apply_panel_order(self) -> None:
        """Ordnet Cockpit-Kacheln passend zum aktiven Layoutmodus an."""
        fixed = self.is_layout_fixed()
        empty_keys = {
            key for key, section in self._sections.items() if section.is_empty()
        }
        left_keys, right_keys = arrange_columns(
            self.PANEL_ORDER_DEFAULTS,
            self._panel_order(),
            self._panel_columns(),
            default_left=self.LEFT_COLUMN_PANELS,
            empty_keys=empty_keys,
            automatic=not fixed,
            legacy_map=_cp.LEGACY_PANEL_MAP,
        )
        left = [
            self._panel_widgets[key] for key in left_keys if key in self._panel_widgets
        ]
        right = [
            self._panel_widgets[key] for key in right_keys if key in self._panel_widgets
        ]
        self.columns.set_columns(left, right)
        self.columns.set_drag_enabled(
            fixed,
            tooltip=tr("cockpit.drag_handle_tip"),
            drop_text=tr("cockpit.drop_here"),
        )

    # ── Panel visibility ────────────────────────────────────────
    def _panel_config(self) -> dict[str, bool]:
        # v2.2.22: der wirksame Zustand kommt zentral aus utils/cockpit_presets –
        # der fruehere {**PANEL_DEFAULTS, **cfg}-Merge mischte die ALL-TRUE-Basis
        # ein und liess beim ersten Toggle im Fokus-Modus alle Panels aufpoppen.
        return _cp.effective_panels(self.settings)

    def _apply_panel_visibility(self) -> None:
        cfg = self._panel_config()
        for key, widget in self._panel_widgets.items():
            # Datenleere Bereiche bleiben sichtbar, schrumpfen kompakt und werden
            # im Automatikmodus nach unten sortiert. Ausblenden geschieht nur noch
            # ausdrücklich über Preset/Benutzerwahl.
            widget.setVisible(bool(cfg.get(key, True)))

    def _show_customize_menu(self) -> None:
        """Cockpit-Bereiche ein-/ausblenden und Reihenfolge sortieren."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("cockpit.customize_title"))
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)

        info = QLabel(tr("cockpit.customize_intro"))
        info.setWordWrap(True)
        lay.addWidget(info)

        chk_fixed = QCheckBox(tr("cockpit.layout_fixed"))
        chk_fixed.setChecked(self.is_layout_fixed())
        chk_fixed.setToolTip(tr("cockpit.layout_fixed_tip"))
        lay.addWidget(chk_fixed)

        mode_hint = QLabel(tr("cockpit.layout_mode_hint"))
        mode_hint.setObjectName("cockpitModeHint")
        mode_hint.setWordWrap(True)
        lay.addWidget(mode_hint)

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

        reset_requested = False

        def reset_order() -> None:
            nonlocal reset_requested
            reset_requested = True
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
        new_cfg = _cp.effective_panels(self.settings)
        for i in range(lst.count()):
            item = lst.item(i)
            key = item.data(Qt.UserRole)
            order.append(key)
            new_cfg[key] = item.checkState() == Qt.Checked
        self.settings.set("cockpit_visible_panels", new_cfg)
        self.settings.set("cockpit_preset", "custom")
        if reset_requested:
            self.settings.set("cockpit_panel_columns", dict(self.DEFAULT_PANEL_COLUMNS))
            self.settings.set("cockpit_tile_columns", dict(self.DEFAULT_PANEL_COLUMNS))
        fixed = chk_fixed.isChecked()
        self.settings.set("cockpit_layout_mode", LAYOUT_FIXED if fixed else LAYOUT_AUTO)
        self.settings.set("cockpit_tiles_fixed", fixed)
        self._sync_fix_button(fixed)
        self._set_panel_order(order)
        self.layout_mode_changed.emit(fixed)

    def _show_all_panels(self) -> None:
        self.settings.set("cockpit_visible_panels", {k: True for k in _cp.PANEL_KEYS})
        self.settings.set("cockpit_preset", "custom")
        self._apply_panel_visibility()
