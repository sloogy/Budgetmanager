from __future__ import annotations

import calendar
import logging
import sqlite3
from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from model.budget_model import BudgetModel
from model.category_model import CategoryModel
from model.coverage_model import CoverageResult, coverage_from_tracking_rows
from model.savings_goals_model import SavingsGoalBoundsError, SavingsGoalsModel
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from utils.i18n import db_typ_from_display, display_typ, tr, trf
from utils.money import currency_header, format_money
from utils.money import format_short as format_chf
from utils.notifications import show_info, show_warning
from views.delegates.badge_delegate import BadgeDelegate
from views.quick_add_dialog import QuickAddDialog
from views.recurring_bookings_dialog import PendingBooking, RecurringBookingsDialog
from views.savings_goal_messages import show_savings_goal_bounds_warning
from views.type_color_helper import apply_tracking_type_colors
from views.ui_colors import ui_colors

logger = logging.getLogger(__name__)


def _months_de() -> list[str]:
    return [tr(f"month.{i}") for i in range(1, 13)]


class TrackingTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, settings=None):
        super().__init__()
        self.conn = conn
        self.settings = settings
        try:
            self.recent_days = (
                30 if int(getattr(settings, "recent_days", 14)) == 30 else 14
            )
        except Exception:
            self.recent_days = 14
        self.cats = CategoryModel(conn)
        self.model = TrackingModel(conn)
        self.budget = BudgetModel(conn)
        self.tags_model = TagsModel(conn)
        self.savings_model = SavingsGoalsModel(conn)

        # Buttons
        self.btn_add = QPushButton(tr("btn.add") + "…")
        # Quick action: erzeugt Buchungen aus Fixkosten-/Wiederkehrend-Markierungen der Kategorien
        self.btn_fix = QPushButton(tr("btn.recurring_book"))
        self.btn_edit = QPushButton(tr("btn.edit"))
        self.btn_del = QPushButton(tr("btn.delete"))
        self.btn_clear_filters = QPushButton(tr("btn.reset_filters"))

        # Quick Filters
        self.chk_recent = QCheckBox(
            trf(
                "auto.views_tabs_tracking_tab.56_nur_letzte_value_0_tage_48196fae",
                value_0=(self.recent_days),
            )
        )
        self.chk_recent.setChecked(False)

        # ===== ERWEITERTE FILTER =====

        # Typ-Filter
        self.filter_typ = QComboBox()
        # userData = DB-Schlüssel (sprachunabhängig), text = Anzeigename
        for _disp, _key in [
            (tr("typ.Alle"), ""),
            (tr("typ.Ausgaben"), TYP_EXPENSES),
            (tr("typ.Einkommen"), TYP_INCOME),
            (tr("typ.Ersparnisse"), TYP_SAVINGS),
        ]:
            self.filter_typ.addItem(_disp, _key)

        # Kategorie-Filter
        self.filter_category = QComboBox()
        self.filter_category.addItem(tr("tracking.filter.all_categories"))
        self._reload_categories()

        # Datumsfilter
        self.filter_date_from = QDateEdit()
        self.filter_date_from.setCalendarPopup(True)
        self.filter_date_from.setDate(date.today().replace(day=1))  # Erster des Monats
        self.filter_date_from.setDisplayFormat("dd.MM.yyyy")

        self.filter_date_to = QDateEdit()
        self.filter_date_to.setCalendarPopup(True)
        self.filter_date_to.setDate(date.today())
        self.filter_date_to.setDisplayFormat("dd.MM.yyyy")

        self.chk_use_date_filter = QCheckBox(tr("tracking.chk.date_filter"))
        self.chk_use_date_filter.setChecked(False)

        # Betragsfilter
        self.filter_min_amount = QDoubleSpinBox()
        self.filter_min_amount.setRange(0, 999999)
        self.filter_min_amount.setPrefix(f"{currency_header()} ")
        self.filter_min_amount.setValue(0)
        self.filter_min_amount.setSingleStep(10)

        self.filter_max_amount = QDoubleSpinBox()
        self.filter_max_amount.setRange(0, 999999)
        self.filter_max_amount.setPrefix(f"{currency_header()} ")
        self.filter_max_amount.setValue(999999)
        self.filter_max_amount.setSingleStep(10)

        self.chk_use_amount_filter = QCheckBox(tr("tracking.chk.amount_filter"))
        self.chk_use_amount_filter.setChecked(False)

        # Textsuche
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText(tr("tracking.ph.search"))
        self.filter_search.setClearButtonEnabled(True)

        # Tag-Filter
        self.filter_tag = QComboBox()
        self.filter_tag.addItem(tr("tracking.filter.all_tags"), None)
        self._reload_tags()

        # Summen-Label
        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("font-weight: bold; padding: 5px;")

        # Deckungswarnung: gebuchte Ausgaben + Ersparnisse dürfen Einkommen nicht übersteigen.
        self.lbl_coverage_warning = QLabel("")
        self.lbl_coverage_warning.setWordWrap(True)
        self.lbl_coverage_warning.setVisible(False)
        self.lbl_coverage_warning.setTextFormat(Qt.RichText)

        # Kontext-Panel: aktive Sparziele nur dort anzeigen, wo sie beim Buchen relevant sind.
        # Wenn keine aktiven Ziele existieren, bleibt der Bereich komplett ausgeblendet.
        self.savings_panel = self._build_savings_panel()

        # Tabelle
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                tr("header.date"),
                tr("header.type"),
                tr("header.category"),
                currency_header(),
                tr("header.description"),
                tr("header.tags"),
                tr("auto.views_tabs_tracking_tab.119_id_db302b9b"),
            ]
        )

        # Accessibility: Header-Tooltips
        _hdr = self.table.horizontalHeader()
        for _i, _tip in enumerate(
            [
                tr("tracking.tip.col_date"),
                tr("tracking.tip.col_type"),
                tr("tracking.tip.col_category"),
                tr("tracking.tip.col_amount"),
                tr("tracking.tip.col_details"),
                tr("header.tags"),
            ]
        ):
            if _i < self.table.columnCount():
                self.table.horizontalHeaderItem(_i).setToolTip(_tip)
        # Badge/Pillen Darstellung für Typ-Spalte
        self._badge_delegate = BadgeDelegate(
            self.table, color_map=self.settings.get("type_colors", {})
        )
        self.table.setItemDelegateForColumn(1, self._badge_delegate)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnHidden(6, True)  # internal id
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self._apply_stable_column_widths()

        # Debounce-Timer: bei Filter-Änderungen nur 1× refreshen
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self.refresh)

        # === LAYOUTS ===

        # Button-Leiste (kompakt - nur Hinzufügen und Löschen)
        top = QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_fix)
        top.addWidget(self.btn_del)
        top.addStretch(1)
        top.addWidget(self.chk_recent)
        # btn_edit ist im Menü "Bearbeiten" verfügbar
        self.btn_edit.setVisible(False)

        # Filter-GroupBox
        filter_group = QGroupBox(tr("tracking.grp.filters"))
        filter_layout = QVBoxLayout()

        # Zeile 1: Typ und Kategorie
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(tr("lbl.type")))
        row1.addWidget(self.filter_typ, 1)
        row1.addWidget(QLabel(tr("lbl.category")))
        row1.addWidget(self.filter_category, 2)
        row1.addWidget(QLabel(tr("lbl.tag")))
        row1.addWidget(self.filter_tag, 1)
        filter_layout.addLayout(row1)

        # Zeile 2: Datumsfilter
        row2 = QHBoxLayout()
        row2.addWidget(self.chk_use_date_filter)
        row2.addWidget(QLabel(tr("lbl.from")))
        row2.addWidget(self.filter_date_from)
        row2.addWidget(QLabel(tr("lbl.to")))
        row2.addWidget(self.filter_date_to)
        row2.addStretch(1)
        filter_layout.addLayout(row2)

        # Zeile 3: Betragsfilter
        row3 = QHBoxLayout()
        row3.addWidget(self.chk_use_amount_filter)
        row3.addWidget(QLabel(tr("lbl.min")))
        row3.addWidget(self.filter_min_amount)
        row3.addWidget(QLabel(tr("lbl.max")))
        row3.addWidget(self.filter_max_amount)
        row3.addStretch(1)
        filter_layout.addLayout(row3)

        # Zeile 4: Textsuche und Reset
        row4 = QHBoxLayout()
        row4.addWidget(QLabel(tr("lbl.search")))
        row4.addWidget(self.filter_search, 3)
        row4.addWidget(self.btn_clear_filters)
        filter_layout.addLayout(row4)

        filter_group.setLayout(filter_layout)

        # Hauptlayout
        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(filter_group)
        root.addWidget(self.savings_panel)
        root.addWidget(self.lbl_summary)
        root.addWidget(self.lbl_coverage_warning)
        root.addWidget(self.table)
        self.setLayout(root)

        # === SIGNALS ===
        self.btn_add.clicked.connect(self.add)
        self.btn_fix.clicked.connect(self.add_fixcosts)
        self.btn_edit.clicked.connect(self.edit)
        self.btn_del.clicked.connect(self.delete)
        self.btn_clear_filters.clicked.connect(self.clear_filters)

        # Filter-Änderungen triggern debounced refresh (200ms)
        self.chk_recent.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_typ.currentIndexChanged.connect(lambda _: self._on_typ_changed())
        self.filter_category.currentIndexChanged.connect(
            lambda _: self._delayed_refresh()
        )
        self.chk_use_date_filter.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_date_from.dateChanged.connect(lambda _: self._delayed_refresh())
        self.filter_date_to.dateChanged.connect(lambda _: self._delayed_refresh())
        self.chk_use_amount_filter.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_min_amount.valueChanged.connect(lambda _: self._delayed_refresh())
        self.filter_max_amount.valueChanged.connect(lambda _: self._delayed_refresh())
        self.filter_search.textChanged.connect(lambda _: self._delayed_refresh())
        self.filter_tag.currentIndexChanged.connect(lambda _: self._delayed_refresh())

        self.table.doubleClicked.connect(lambda _: self.edit())

        self.refresh()

    def _apply_stable_column_widths(self) -> None:
        """Fixiert Hauptspalten, damit Tabellenbreiten nach Settings-Reload stabil bleiben."""
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        fixed_widths = {
            0: 105,  # Datum
            1: 120,  # Typ
            2: 220,  # Kategorie
            3: 115,  # Betrag
            5: 160,  # Tags
            6: 55,  # interne ID (versteckt)
        }
        for col, width in fixed_widths.items():
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(6, True)

    def _build_savings_panel(self) -> QGroupBox:
        """Kompakte Sparziel-Leiste für Buchungen/Tracking.

        Designentscheidung:
        - Nicht dauerhaft omnipräsent.
        - Sichtbar nur, wenn aktive Ziele existieren.
        - Doppelklick öffnet direkt das konkrete Sparziel.
        """
        panel = QGroupBox(tr("tracking.savings_panel.title"))
        panel.setToolTip(tr("tracking.savings_panel.tooltip"))
        layout = QVBoxLayout(panel)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.lbl_savings_panel_hint = QLabel(tr("tracking.savings_panel.empty"))
        self.lbl_savings_panel_hint.setWordWrap(True)
        header.addWidget(self.lbl_savings_panel_hint, 1)
        self.btn_manage_savings_goals = QPushButton(tr("tracking.savings_panel.manage"))
        self.btn_manage_savings_goals.setToolTip(
            tr("tracking.savings_panel.manage_tip")
        )
        self.btn_manage_savings_goals.clicked.connect(
            lambda: self._open_savings_goal(None)
        )
        header.addWidget(self.btn_manage_savings_goals)
        layout.addLayout(header)

        self.savings_table = QTableWidget(0, 4)
        self.savings_table.setHorizontalHeaderLabels(
            [
                tr("tracking.savings_panel.goal"),
                tr("tracking.savings_panel.progress"),
                tr("tracking.savings_panel.remaining"),
                tr("tracking.savings_panel.status"),
            ]
        )
        self.savings_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.savings_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.savings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.savings_table.verticalHeader().setVisible(False)
        self.savings_table.setAlternatingRowColors(True)
        self.savings_table.setMaximumHeight(150)
        self.savings_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_view = self.savings_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.savings_table.doubleClicked.connect(
            lambda _: self._open_selected_savings_goal()
        )
        layout.addWidget(self.savings_table)

        panel.setVisible(False)
        return panel

    def _refresh_savings_panel(self) -> None:
        """Aktive Sparziele im Tracking anzeigen; ohne aktive Ziele ausblenden."""
        try:
            goals = [
                g
                for g in self.savings_model.list_all()
                if not getattr(g, "is_completed", False)
            ]
        except Exception as exc:
            logger.debug("Sparziele-Panel konnte nicht geladen werden: %s", exc)
            goals = []

        if not goals:
            self.savings_panel.setVisible(False)
            return

        self.savings_panel.setVisible(True)
        self.savings_table.setRowCount(0)
        self.lbl_savings_panel_hint.setText(
            trf("tracking.savings_panel.hint", count=len(goals))
        )
        colors = ui_colors(self)

        for goal in goals:
            row = self.savings_table.rowCount()
            self.savings_table.insertRow(row)

            name = f"{getattr(goal, 'status_icon', '')} {goal.name}".strip()
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, goal.id)
            tip_parts = []
            if goal.category:
                tip_parts.append(
                    trf("tracking.savings_panel.tip_category", category=goal.category)
                )
            if goal.deadline:
                tip_parts.append(
                    trf("tracking.savings_panel.tip_deadline", deadline=goal.deadline)
                )
            tip_parts.extend(
                [
                    trf(
                        "savings.tooltip.contributed",
                        amount=format_money(goal.contributed_amount),
                    ),
                    trf(
                        "savings.tooltip.used",
                        amount=format_money(goal.withdrawn_amount),
                    ),
                    trf(
                        "savings.tooltip.stock", amount=format_money(goal.current_stock)
                    ),
                    tr("tracking.savings_panel.tip_open"),
                ]
            )
            name_item.setToolTip("\n".join(tip_parts))
            self.savings_table.setItem(row, 0, name_item)

            progress_value = max(0, min(100, int(getattr(goal, "progress_percent", 0))))
            pw = QWidget()
            pl = QHBoxLayout(pw)
            pl.setContentsMargins(4, 2, 4, 2)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(progress_value)
            bar.setFormat(f"{progress_value}%")
            bar.setFixedHeight(18)
            if progress_value >= 100:
                chunk = colors.ok
            elif progress_value >= 60:
                chunk = colors.accent
            elif progress_value >= 25:
                chunk = colors.warning
            else:
                chunk = colors.negative
            bar.setStyleSheet(
                f"""
                QProgressBar {{
                    border: 1px solid {colors.border};
                    border-radius: 4px;
                    text-align: center;
                    background: {colors.bg_panel};
                }}
                QProgressBar::chunk {{
                    background-color: {chunk};
                    border-radius: 3px;
                }}
            """
            )
            pl.addWidget(bar)
            self.savings_table.setCellWidget(row, 1, pw)

            remaining_item = QTableWidgetItem(
                format_money(getattr(goal, "remaining_contribution", 0))
            )
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.savings_table.setItem(row, 2, remaining_item)

            status_item = QTableWidgetItem(getattr(goal, "status_label", ""))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.savings_table.setItem(row, 3, status_item)

        self.savings_table.resizeRowsToContents()

    def _selected_savings_goal_id(self) -> int | None:
        row = self.savings_table.currentRow()
        if row < 0:
            return None
        item = self.savings_table.item(row, 0)
        if item is None:
            return None
        try:
            value = item.data(Qt.UserRole)
            return int(value) if value is not None else None
        except Exception:
            return None

    def _open_selected_savings_goal(self) -> None:
        self._open_savings_goal(self._selected_savings_goal_id())

    def _open_savings_goal(self, goal_id: int | None = None) -> None:
        from views.savings_goals_dialog import SavingsGoalsDialog

        dialog = SavingsGoalsDialog(self.window(), self.conn, initial_goal_id=goal_id)
        dialog.exec()
        self._refresh_savings_panel()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return (
            "Alle"
            if self.filter_typ.currentIndex() == 0
            else self.filter_typ.currentText()
        )

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def _reload_categories(self):
        """Lädt alle Kategorien in den Filter (Tree-fähig)"""
        current_data = (
            self.filter_category.currentData()
            or self.filter_category.currentText().strip()
        )
        self.filter_category.clear()
        self.filter_category.addItem(tr("tracking.filter.all_categories"), None)

        # In 'Alle' zeigen wir Typ-Prefix zur besseren Unterscheidung
        rows = []
        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
            pairs = []
            if hasattr(self.cats, "list_names_tree"):
                try:
                    pairs = self.cats.list_names_tree(typ)
                except Exception:
                    pairs = []
            if pairs:
                for label, real in pairs:
                    rows.append(
                        (
                            trf(
                                "tracking.filter.typ_prefix",
                                typ=display_typ(typ),
                                label=label,
                            ),
                            (typ, real),
                        )
                    )
            else:
                for cat in self.cats.list_names(typ):
                    rows.append(
                        (
                            trf(
                                "tracking.filter.typ_prefix",
                                typ=display_typ(typ),
                                label=cat,
                            ),
                            (typ, cat),
                        )
                    )

        # sort by display text
        for disp, real in sorted(rows, key=lambda x: str(x[0]).lower()):
            self.filter_category.addItem(disp, real)

        # Auswahl wiederherstellen
        if current_data:
            for i in range(self.filter_category.count()):
                data_i = self.filter_category.itemData(i)
                data_cat = (
                    data_i[1]
                    if isinstance(data_i, tuple) and len(data_i) == 2
                    else data_i
                )
                if (
                    data_i == current_data
                    or data_cat == current_data
                    or self.filter_category.itemText(i)
                    .strip()
                    .endswith(str(current_data))
                ):
                    self.filter_category.setCurrentIndex(i)
                    break

    def _reload_tags(self):
        """Lädt alle Tags in den Tag-Filter."""
        current_data = self.filter_tag.currentData()
        self.filter_tag.clear()
        self.filter_tag.addItem(tr("tracking.filter.all_tags"), None)
        try:
            for tag in self.tags_model.list_all():
                self.filter_tag.addItem(tag.name, tag.id)
        except Exception as e:
            logger.debug("for tag in self.tags_model.list_all():: %s", e)
        # Auswahl wiederherstellen
        if current_data is not None:
            for i in range(self.filter_tag.count()):
                if self.filter_tag.itemData(i) == current_data:
                    self.filter_tag.setCurrentIndex(i)
                    break

    def _on_typ_changed(self):
        """Wenn Typ geändert wird, Kategorien-Filter anpassen"""
        typ = self._current_filter_typ_db()
        if typ == "Alle":
            self._reload_categories()
        else:
            current_data = (
                self.filter_category.currentData()
                or self.filter_category.currentText().strip()
            )
            self.filter_category.clear()
            self.filter_category.addItem(tr("tracking.filter.all_categories"), None)

            pairs = []
            if hasattr(self.cats, "list_names_tree"):
                try:
                    pairs = self.cats.list_names_tree(typ)
                except Exception:
                    pairs = []

            if pairs:
                for label, real in pairs:
                    self.filter_category.addItem(label, real)
            else:
                for cat in self.cats.list_names(typ):
                    self.filter_category.addItem(cat, cat)

            if current_data:
                for i in range(self.filter_category.count()):
                    if self.filter_category.itemData(
                        i
                    ) == current_data or self.filter_category.itemText(
                        i
                    ).strip() == str(
                        current_data
                    ):
                        self.filter_category.setCurrentIndex(i)
                        break

        self._delayed_refresh()

    def _delayed_refresh(self):
        """Debounced: Timer (re-)starten – refresh() wird erst nach 200ms Ruhe ausgelöst."""
        self._refresh_timer.stop()
        self._refresh_timer.start()

    def _show_context_menu(self, pos):
        """Rechtsklick-Kontextmenü auf der Tracking-Tabelle."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        act_edit = menu.addAction(tr("btn.edit"))
        act_tags = menu.addAction(tr("tracking.ctx.set_tags"))
        menu.addSeparator()
        act_duplicate = menu.addAction(tr("tracking.ctx.duplicate"))
        menu.addSeparator()
        act_delete = menu.addAction(tr("btn.delete"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self.edit()
        elif chosen == act_tags:
            self._set_tags_for_selected()
        elif chosen == act_duplicate:
            self._duplicate_selected()
        elif chosen == act_delete:
            self.delete()

    def _create_tag_inline_for_tracking(self) -> int | None:
        """Erstellt ein Tag direkt aus 'Tag setzen'."""
        name, ok = QInputDialog.getText(
            self, tr("tags.create_title"), tr("tags.create_name_label")
        )
        if not ok or not name.strip():
            return None
        name = name.strip()
        if self.tags_model.name_exists(name):
            show_warning(
                self,
                tr("auto.views_tags_manager_dialog.221_tag_existiert_20291c3b"),
                trf(
                    "auto.views_tags_manager_dialog.222_ein_tag_mit_dem_namen_value_0_exist_be543b1c",
                    value_0=name,
                ),
            )
            return None
        action_text, ok_action = QInputDialog.getText(
            self,
            tr("tags.action_text_title"),
            tr("tags.action_text_label"),
            text="",
        )
        if not ok_action:
            action_text = ""
        return self.tags_model.create_tag(name, action_text=action_text.strip())

    def _set_tags_for_selected(self):
        """Dialog zum Setzen von Tags für den ausgewählten Eintrag."""
        sel = self.table.currentRow()
        if sel < 0:
            return
        entry_id = int(self.table.item(sel, 6).text())

        all_tags = self.tags_model.list_all()
        if not all_tags:
            # Linksklick auf 'Tag setzen' ohne vorhandene Tags öffnet direkt
            # das Tag-Erstellungsmenü statt nur eine Sackgassen-Meldung.
            new_id = self._create_tag_inline_for_tracking()
            if not new_id:
                return
            all_tags = self.tags_model.list_all()

        current_tags = self.tags_model.get_tags_for_entry(entry_id)
        current_ids = {t["id"] for t in current_tags}
        row_typ = (
            db_typ_from_display(self.table.item(sel, 1).text())
            if self.table.item(sel, 1)
            else ""
        )
        row_cat = self.table.item(sel, 2).text() if self.table.item(sel, 2) else ""
        fixed_ids = set(self.tags_model.get_tag_ids_for_category_name(row_typ, row_cat))
        current_ids |= fixed_ids

        # Einfacher Checkable-Dialog
        from PySide6.QtWidgets import QDialogButtonBox, QListWidget, QListWidgetItem

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("tracking.title.set_tags"))
        dlg.setMinimumWidth(300)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(trf("tracking.lbl.tags_for_entry", entry_id=entry_id)))

        lw = QListWidget()
        for tag in all_tags:
            label = f"{tag.name}  🔒" if tag.id in fixed_ids else tag.name
            item = QListWidgetItem(label)
            item.setCheckState(Qt.Checked if tag.id in current_ids else Qt.Unchecked)
            item.setData(Qt.UserRole, tag.id)
            if tag.id in fixed_ids:
                item.setFlags(
                    (item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsUserCheckable
                )
                item.setToolTip(tr("tags.fixed_category_tag_tip"))
            else:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            lw.addItem(item)
        layout.addWidget(lw)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)

        if dlg.exec() == QDialog.Accepted:
            new_ids = []
            for i in range(lw.count()):
                item = lw.item(i)
                if item.checkState() == Qt.Checked:
                    new_ids.append(item.data(Qt.UserRole))
            self.tags_model.set_entry_tags(entry_id, new_ids)
            try:
                current_details = (
                    self.table.item(sel, 4).text() if self.table.item(sel, 4) else ""
                )
                if not current_details.strip():
                    action_details = self.tags_model.render_action_texts(
                        new_ids,
                        category=row_cat,
                        booking_date=date.today(),
                    )
                    if action_details:
                        self.conn.execute(
                            "UPDATE tracking SET details=? WHERE id=?",
                            (action_details, int(entry_id)),
                        )
                        self.conn.commit()
            except Exception as exc:
                logger.debug("Tag-Aktionstext fuer bestehende Buchung: %s", exc)
            self._reload_tags()
            self.refresh()

    def _duplicate_selected(self):
        """Dupliziert den ausgewählten Eintrag (mit heutigem Datum)."""
        row_id = self._selected_id()
        if row_id is None:
            return
        r = self.table.currentRow()
        typ = self.table.item(r, 1).text()
        cat = self.table.item(r, 2).text()
        amt_txt = (
            self.table.item(r, 3).text().replace("'", "").replace(",", ".").strip()
        )
        try:
            amt = float(amt_txt)
        except Exception:
            amt = 0.0
        details = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
        new_id = self.model.add(
            date.today(), db_typ_from_display(typ), cat, amt, details
        )
        try:
            self.tags_model.set_entry_tags(
                int(new_id),
                [t["id"] for t in self.tags_model.get_tags_for_entry(int(row_id))],
            )
        except Exception as exc:
            logger.debug("duplicate tags: %s", exc)
        self.refresh()

    def clear_filters(self):
        """Setzt alle Filter zurück"""
        self.filter_typ.setCurrentIndex(0)
        self.filter_category.setCurrentIndex(0)
        self.filter_tag.setCurrentIndex(0)
        self.chk_use_date_filter.setChecked(False)
        self.filter_date_from.setDate(date.today().replace(day=1))
        self.filter_date_to.setDate(date.today())
        self.chk_use_amount_filter.setChecked(False)
        self.filter_min_amount.setValue(0)
        self.filter_max_amount.setValue(999999)
        self.filter_search.clear()
        self.chk_recent.setChecked(False)

    def _selected_id(self) -> int | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 6)
        if not it:
            return None
        try:
            return int(it.text())
        except Exception:
            return None

    def set_recent_days(self, days: int):
        """Setzt den Zeitraum für den Quick-Filter (nur 14 oder 30)."""
        self.recent_days = 30 if int(days) == 30 else 14
        self.chk_recent.setText(
            trf(
                "auto.views_tabs_tracking_tab.457_nur_letzte_value_0_tage_be9a083a",
                value_0=(self.recent_days),
            )
        )
        # Wenn Quick-Filter aktiv ist, sofort neu laden
        if self.chk_recent.isChecked():
            self.refresh()

    def _format_coverage_suggestion(self, result: CoverageResult) -> str:
        """Formatiert Spar-Vorschläge aus gebuchten Ersparnissen."""
        singles = result.single_savings_suggestions()
        if singles:
            top = singles[0]
            return trf(
                "coverage.suggestion_single",
                category=top.category,
                amount=format_money(result.deficit),
            )
        combined = result.combined_savings_suggestions()
        if combined:
            parts = ", ".join(
                f"{s.category} {format_money(s.amount)}" for s in combined[:4]
            )
            if len(combined) > 4:
                parts += " …"
            return trf("coverage.suggestion_combined", categories=parts)
        return tr("coverage.no_savings_suggestion")

    def _update_tracking_coverage_warning(self, rows) -> None:
        """Warnt, wenn die sichtbare Gesamtauswertung nicht durch Einkommen gedeckt ist.

        Die Warnung ist bewusst nur beim Konto-Filter „Alle” aktiv. Bei einem
        reinen Ausgaben- oder Ersparnisse-Filter wäre Einkommen zwangsläufig 0
        und die Warnung würde falsch positiv wirken.
        """
        try:
            settings_obj = self.settings
            if settings_obj is None:
                from settings import Settings

                settings_obj = Settings()
            if not bool(settings_obj.get("warn_budget_overrun", False)):
                self.lbl_coverage_warning.clear()
                self.lbl_coverage_warning.setVisible(False)
                return

            if not self._is_all_typ():
                self.lbl_coverage_warning.clear()
                self.lbl_coverage_warning.setVisible(False)
                return
            result = coverage_from_tracking_rows(rows)
            if not result.is_overdrawn:
                self.lbl_coverage_warning.clear()
                self.lbl_coverage_warning.setVisible(False)
                return
            c = ui_colors(self)
            self.lbl_coverage_warning.setStyleSheet(
                f"color: {c.negative}; background-color: {c.error_bg}; "
                "font-weight: bold; padding: 6px; border-radius: 4px;"
            )
            text = trf(
                "tracking.coverage.warning",
                deficit=format_money(result.deficit),
                suggestion=self._format_coverage_suggestion(result),
            )
            self.lbl_coverage_warning.setText(text)
            self.lbl_coverage_warning.setToolTip(
                f"{tr('kpi.income')}: {format_money(result.income)}\n"
                f"{tr('kpi.expenses')}: {format_money(result.expenses)}\n"
                f"{tr('typ.Ersparnisse')}: {format_money(result.savings)}\n"
                f"{tr('lbl.saldo')}: {format_money(result.balance)}"
            )
            self.lbl_coverage_warning.setVisible(True)
        except Exception as exc:
            logger.debug(
                "Tracking-Deckungswarnung konnte nicht berechnet werden: %s", exc
            )
            self.lbl_coverage_warning.clear()
            self.lbl_coverage_warning.setVisible(False)

    def _selected_filter_category(self) -> tuple[str | None, str | None]:
        """Liest den Kategorie-Filter sprach- und hierarchiesicher aus.

        In der Konto-Auswahl "Alle" enthält itemData ein Tupel (typ, name), damit
        gleichnamige Kategorien verschiedener Konten nicht verwechselt werden.
        In konto-spezifischen Filtern bleibt itemData der Kategoriename.
        """
        data = self.filter_category.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            typ, category = data
            return (str(typ) if typ else None, str(category) if category else None)
        if isinstance(data, str) and data.strip():
            typ = None if self._is_all_typ() else self._current_filter_typ_db()
            return typ, data.strip()
        return (None, None)

    def _expanded_filter_categories(
        self, typ: str | None, category: str | None
    ) -> list[str] | None:
        """Erweitert einen Parent-Filter auf alle Children.

        Beispiel: Filter "Wohnen" zeigt auch "Miete", "Strom" usw. Ohne Treffer
        fällt die Funktion auf die gewählte Kategorie zurück.
        """
        if not category:
            return None
        typ_candidates = [typ] if typ else [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]
        expanded: list[str] = []
        for typ_candidate in typ_candidates:
            if not typ_candidate:
                continue
            try:
                names = self.cats.descendant_names(
                    typ_candidate, category, include_self=True
                )
            except Exception as exc:
                logger.debug(
                    "Parent-Kategorie-Filter konnte nicht erweitert werden: %s", exc
                )
                names = [category]
            for name in names:
                if name and name not in expanded:
                    expanded.append(str(name))
        return expanded or [category]

    def refresh(self):
        """Lädt Daten mit aktiven Filtern"""

        # Quick Filter: Letzte 14 Tage
        if self.chk_recent.isChecked():
            rows = self.model.list_recent_sorted(self.recent_days)
        else:
            # Erweiterte Filter verwenden
            typ = self._current_filter_typ_db() if not self._is_all_typ() else None
            selected_typ, category = self._selected_filter_category()
            if typ is None and selected_typ:
                # In Konto-Filter "Alle" steckt der echte Typ in der Kategorie-Auswahl.
                typ = selected_typ
            categories = self._expanded_filter_categories(typ, category)

            date_from = None
            date_to = None
            if self.chk_use_date_filter.isChecked():
                date_from = self.filter_date_from.date().toPython()
                date_to = self.filter_date_to.date().toPython()

            min_amount = None
            max_amount = None
            if self.chk_use_amount_filter.isChecked():
                min_amount = self.filter_min_amount.value()
                max_amount = self.filter_max_amount.value()

            search_text = self.filter_search.text().strip() or None

            # Tag-Filter
            tag_id = self.filter_tag.currentData()

            rows = self.model.list_filtered(
                typ=typ,
                category=None,
                categories=categories,
                date_from=date_from,
                date_to=date_to,
                min_amount=min_amount,
                max_amount=max_amount,
                search_text=search_text,
                tag_id=tag_id,
            )

        # Tabelle füllen
        self.table.setRowCount(0)
        total_ausgaben = 0.0
        total_einkommen = 0.0
        total_ersparnisse = 0.0

        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r.d.strftime("%d.%m.%Y")))
            self.table.setItem(i, 1, QTableWidgetItem(display_typ(str(r.typ))))
            # v2.2.1 (Bericht-Punkt 4): Kurzlabel in der Zelle, voller Pfad
            # "Parent › Kind" als Tooltip – konsistent zur Schnellerfassung
            # und ohne überbreite Kategorie-Spalte bei tiefen Hierarchien.
            _cat_name = str(r.category)
            _cat_full = self.cats.display_with_parent(str(r.typ), _cat_name)
            _cat_item = QTableWidgetItem(_cat_name)
            if _cat_full != _cat_name:
                _cat_item.setToolTip(_cat_full)
            self.table.setItem(i, 2, _cat_item)
            a = QTableWidgetItem(format_chf(float(r.amount)))
            a.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 3, a)
            self.table.setItem(i, 4, QTableWidgetItem(str(r.details)))
            try:
                _tags = self.tags_model.get_tags_for_entry(int(r.id))
                _tag_txt = ", ".join(
                    str(t.get("name", "")) for t in _tags if str(t.get("name", ""))
                )
            except Exception as exc:
                logger.debug("entry tags display: %s", exc)
                _tag_txt = ""
            self.table.setItem(i, 5, QTableWidgetItem(_tag_txt))
            self.table.setItem(i, 6, QTableWidgetItem(str(r.id)))

            # Summen berechnen
            if r.typ == TYP_EXPENSES:
                total_ausgaben += r.amount
            elif r.typ == TYP_INCOME:
                total_einkommen += r.amount
            elif r.typ == TYP_SAVINGS:
                total_ersparnisse += r.amount

        self._apply_stable_column_widths()

        # Summen anzeigen
        saldo = total_einkommen - total_ausgaben - total_ersparnisse
        summary_text = trf(
            "tracking.summary",
            count=len(rows),
            income=format_money(total_einkommen),
            expenses=format_money(total_ausgaben),
            savings=format_money(total_ersparnisse),
            balance=format_money(saldo),
        )
        self.lbl_summary.setText(summary_text)
        self._update_tracking_coverage_warning(rows)
        self._refresh_savings_panel()
        # Typ- und Negativfarben anwenden (vom Theme Manager holen)
        type_colors = {}
        negative_color = None
        try:
            # Hole MainWindow reference
            main_window = self
            while main_window.parent() is not None:
                main_window = main_window.parent()

            # Hole Farben vom Theme Manager
            if hasattr(main_window, "theme_manager"):
                type_colors = main_window.theme_manager.get_type_colors()
                negative_color = main_window.theme_manager.get_negative_color()
            else:
                # Fallback via ui_colors
                _uc = ui_colors(self)
                type_colors = _uc.type_colors
                negative_color = _uc.negative
        except Exception:
            # Fallback via ui_colors
            _uc = ui_colors(self)
            type_colors = _uc.type_colors
            negative_color = _uc.negative

        try:
            apply_tracking_type_colors(self.table, type_colors, negative_color)
            if hasattr(self, "_badge_delegate") and self._badge_delegate is not None:
                self._badge_delegate.set_colors(type_colors)
                self.table.viewport().update()
        except Exception as e:
            logger.debug("apply_tracking_type_colors(self.table, type_colors: %s", e)

    def add(self):
        """Neue Buchung erfassen.

        Das Tracking-Fenster nutzt bewusst denselben Schnelleingabe-Dialog wie das
        Cockpit. Dadurch sind Suche, Kategorien-Reihenfolge, letzte Auswahl je Konto,
        negative Ersparnisse und die Buttons "Speichern & neu" identisch.
        """
        dlg = QuickAddDialog(self.conn, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.refresh()
        try:
            main_window = (
                self.window() if callable(getattr(self, "window", None)) else None
            )
            if main_window is not None and hasattr(
                main_window, "_save_encrypted_session"
            ):
                main_window._save_encrypted_session()
            if main_window is not None and hasattr(main_window, "statusBar"):
                main_window.statusBar().showMessage(
                    tr("lbl.eintrag_hinzugefuegt"), 2000
                )
        except Exception as exc:
            logger.debug("Tracking QuickAdd Nacharbeiten fehlgeschlagen: %s", exc)

    def _ask_savings_withdrawal(self, conflict: dict, amount: float) -> str:
        """Fragt den Benutzer ob eine negative Buchung auf ein Sparziel ein Bezug oder eine Korrektur ist.

        Args:
            conflict: Dict mit goal_id, goal_name, goal_status, current_amount, target_amount
            amount: Der negative Betrag

        Returns:
            'correction' = normale Korrektur (einfach buchen)
            'withdrawal' = Bezug/Entnahme (buchen + Warnung)
            'cancel' = Abbrechen
        """
        goal_name = conflict["goal_name"]
        goal_status = conflict["goal_status"]
        current = conflict["current_amount"]
        target = conflict["target_amount"]
        abs_amount = abs(amount)

        if goal_status == "sparend":
            msg = trf(
                "tracking.msg.savings_negative_prompt",
                amount=format_money(abs_amount),
                goal=goal_name,
                current=format_money(current),
                target=format_money(target),
            )
            box = QMessageBox(self)
            box.setWindowTitle(tr("tracking.title.savings_withdraw"))
            box.setTextFormat(Qt.RichText)
            box.setText(msg)
            box.setIcon(QMessageBox.Question)

            btn_correction = box.addButton(
                tr("tracking.btn.correction"), QMessageBox.AcceptRole
            )
            btn_withdrawal = box.addButton(
                tr("tracking.btn.withdrawal"), QMessageBox.DestructiveRole
            )
            box.addButton(tr("btn.cancel"), QMessageBox.RejectRole)

            box.exec()
            clicked = box.clickedButton()
            # Kein Treffer heisst abgebrochen (Esc, Fensterkreuz, oder
            # programmatisch geschlossen). Der sichere Ausgang ist "nichts
            # tun" - nicht die Korrektur, die den Sparstand veraendert.
            if clicked == btn_correction:
                return "correction"
            if clicked == btn_withdrawal:
                show_warning(
                    self,
                    tr("msg.info"),
                    trf("tracking.msg.goal_still_saving", goal_name=goal_name)
                    + "\n\n"
                    + tr("tracking.tip.unlock_goal_1")
                    + tr("tracking.tip.unlock_goal_2")
                    + tr("tracking.tip.unlock_goal_3"),
                )
                return "withdrawal"
            return "cancel"

        elif goal_status == "freigegeben":
            # Bei freigegebenen Zielen: einfach informieren, kein Block
            show_info(
                self,
                tr("tracking.title.savings_consumption"),
                trf(
                    "auto.views_tabs_tracking_tab.682_diese_buchung_wird_als_verbrauch_vo_54220c3f",
                    value_0=(goal_name),
                    value_1=(format_money(conflict["current_amount"])),
                    value_2=(format_money(abs_amount)),
                ),
            )
            return "withdrawal"

        return "correction"

    def _collect_pending(self, year: int, month: int):
        """Sammelt fällige Kandidaten für einen Monat.

        v2.2.16 (K3): aus ``add_fixcosts`` extrahiert, damit der vereinheitlichte
        Dialog beim Monatswechsel neu laden kann.
        Returns: (fix_items, recurring_items, optional_items,
                  skipped_existing, skipped_zero)
        """
        month_name = _months_de()[month - 1]
        fix_items: list[PendingBooking] = []
        recurring_items: list[PendingBooking] = []
        optional_items: list[PendingBooking] = []
        skipped_existing = 0
        skipped_zero = 0

        last_day = calendar.monthrange(year, month)[1]
        EPS = 1e-6

        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
            for cat in self.cats.list(typ):
                budget_amt = float(
                    self.budget.get_amount(year, month, typ, cat.name) or 0.0
                )
                booked = float(
                    self.model.get_month_total(year, month, typ, cat.name) or 0.0
                )

                # Buchungsdatum: Tag aus Kategorie (falls gesetzt), sonst Monatsanfang
                day = (
                    int(cat.recurring_day or 1)
                    if (cat.is_recurring or cat.is_fix)
                    else 1
                )
                if day < 1:
                    day = 1
                if day > last_day:
                    day = last_day
                d = date(year, month, day)
                details = f"{month_name} - {cat.name}"

                both_flags = bool(cat.is_fix and cat.is_recurring)
                single_flag = bool(cat.is_fix) ^ bool(cat.is_recurring)
                no_flags = not (cat.is_fix or cat.is_recurring)

                if both_flags:
                    # Echte Fixkosten (fix UND wiederkehrend): fixer Betrag, einmal pro Monat.
                    # "Abgeschlossen", sobald irgendeine Buchung existiert.
                    if self.model.exists_in_month(
                        year=year, month=month, typ=typ, category=cat.name
                    ):
                        skipped_existing += 1
                        continue
                    if abs(budget_amt) < EPS:
                        skipped_zero += 1
                        continue
                    fix_items.append(
                        PendingBooking(
                            d=d,
                            typ=typ,
                            category=cat.name,
                            amount=budget_amt,
                            details=details,
                            source="auto_fixcost",
                            is_fix=True,
                            is_recurring=True,
                            budget=budget_amt,
                            booked=booked,
                        )
                    )
                    continue

                if single_flag:
                    # Fix XOR wiederkehrend: NICHT als abgeschlossen werten, solange der
                    # Budgetbetrag im Monat nicht erreicht ist. Buchbarer Betrag editierbar,
                    # vorbelegt mit dem noch offenen Restbetrag.
                    if abs(budget_amt) < EPS:
                        # Kein Budget gesetzt -> im Autobuchungsdialog nicht anzeigen.
                        skipped_zero += 1
                        continue
                    else:
                        # Budget bereits erreicht? (Vorzeichen-unabhängig)
                        if abs(booked) >= abs(budget_amt) - EPS:
                            skipped_existing += 1
                            continue
                        remaining = budget_amt - booked
                    if abs(remaining) < EPS:
                        skipped_zero += 1
                        continue

                    src = "auto_fixcost" if cat.is_fix else "auto_recurring"
                    recurring_items.append(
                        PendingBooking(
                            d=d,
                            typ=typ,
                            category=cat.name,
                            amount=float(remaining),
                            details=details,
                            source=src,
                            is_fix=bool(cat.is_fix),
                            is_recurring=bool(cat.is_recurring),
                            budget=budget_amt,
                            booked=booked,
                        )
                    )
                    continue

                if no_flags:
                    # Optionale Budgetposten: keine Monatsautomatik, aber auf Wunsch
                    # im Autobuchungsdialog sichtbar. Null-Budgets werden bewusst
                    # ausgeblendet, damit der Dialog nicht mit leeren Kategorien volläuft.
                    if abs(budget_amt) < EPS:
                        skipped_zero += 1
                        continue
                    if abs(booked) >= abs(budget_amt) - EPS:
                        skipped_existing += 1
                        continue
                    remaining = budget_amt - booked
                    if abs(remaining) < EPS:
                        skipped_zero += 1
                        continue
                    optional_items.append(
                        PendingBooking(
                            d=d,
                            typ=typ,
                            category=cat.name,
                            amount=float(remaining),
                            details=details,
                            source="auto_optional",
                            is_fix=False,
                            is_recurring=False,
                            budget=budget_amt,
                            booked=booked,
                        )
                    )
                    continue

        return (
            fix_items,
            recurring_items,
            optional_items,
            skipped_existing,
            skipped_zero,
        )

    def add_fixcosts(self):
        """v2.2.16 (K3): EIN Dialog für fällige Buchungen.

        Vorher: FixcostDialog (nur Monatsauswahl) → je nach Bestand entweder
        RecurringBookingsDialog ODER Ja/Nein-Frage + MissingBookingsDialog.
        Jetzt: Monatsauswahl lebt im Dialog selbst; auch der Nur-Fixkosten-Fall
        nutzt dieselbe Liste (Fixkosten sind vorangehakt – "alle buchen" ist
        ein OK-Klick).
        """
        today = date.today()
        year, month = today.year, today.month

        fix_items, recurring_items, optional_items, skipped_existing, skipped_zero = (
            self._collect_pending(year, month)
        )

        # v2.2.17 (Logikfix F1): Nur abbrechen, wenn es ueberhaupt keine
        # relevanten Kategorien gibt. "Aktueller Monat komplett gebucht" ist
        # KEIN Grund mehr, den Dialog zu verweigern – sonst waere der
        # integrierte Monatswechsel (K3) unerreichbar.
        has_candidates = bool(fix_items or recurring_items or optional_items)
        if not has_candidates and skipped_existing == 0 and skipped_zero == 0:
            show_info(
                self,
                tr("msg.info"),
                tr("tracking.msg.no_fix_or_recurring")
                + "\n"
                + tr("tracking.tip.set_budget_and_mark_fix"),
            )
            return

        def _reload(y: int, m: int):
            f, r, o, _se, _sz = self._collect_pending(y, m)
            return f, r, o

        dlg_book = RecurringBookingsDialog(
            self,
            fix_items=fix_items,
            recurring_items=recurring_items,
            optional_items=optional_items,
            initial_month=(year, month),
            reload_callback=_reload,
        )
        if dlg_book.exec() != QDialog.Accepted:
            return
        to_book = dlg_book.selected_items()

        # v2.2.17 (Logikfix F4): Die Ergebnis-Statistik muss sich auf den im
        # Dialog GEWAEHLTEN Monat beziehen, nicht auf den Startmonat.
        final_month = dlg_book.current_month() or (year, month)
        _f, _r, _o, skipped_existing, skipped_zero = self._collect_pending(*final_month)

        inserted = 0
        skipped_zero_book = 0
        from model.crypto import coalesced_commits

        with coalesced_commits(self.conn):
            for it in to_book:
                if abs(float(it.amount)) < 1e-9:
                    skipped_zero_book += 1
                    continue
                self.model.add(
                    it.d,
                    it.typ,
                    it.category,
                    float(it.amount),
                    it.details,
                    source=getattr(it, "source", "manual"),
                )
                inserted += 1

        show_info(
            self,
            "OK",
            trf(
                "tracking.msg.fixcosts_result",
                inserted=inserted,
                skipped_existing=skipped_existing,
                skipped_zero=skipped_zero,
                skipped_zero_book=skipped_zero_book,
            ),
        )
        self.refresh()

    def edit(self):
        row_id = self._selected_id()
        if row_id is None:
            show_info(self, tr("msg.info"), tr("msg.no_selection"))
            return

        r = self.table.currentRow()
        d = self.table.item(r, 0).text()
        typ = self.table.item(r, 1).text()
        cat = self.table.item(r, 2).text()
        amt_txt = (
            self.table.item(r, 3).text().replace("'", "").replace(",", ".").strip()
        )
        try:
            amt = float(amt_txt)
        except Exception:
            amt = 0.0
        details = self.table.item(r, 4).text() if self.table.item(r, 4) else ""

        try:
            tag_ids = [
                int(t["id"]) for t in self.tags_model.get_tags_for_entry(int(row_id))
            ]
        except Exception:
            tag_ids = []
        # v2.2.16 (K1): Bearbeiten nutzt denselben QuickAddDialog wie das
        # Anlegen (Edit-Modus). Der Dialog speichert selbst (inkl. Tags,
        # Sparziel-Grenzen und Aktionstexten) – hier nur noch auffrischen.
        dlg = QuickAddDialog(
            self.conn,
            self,
            preset={
                "date": d,
                "typ": typ,
                "category": cat,
                "amount": amt,
                "details": details,
                "tag_ids": tag_ids,
                "savings_action": self.model.get_savings_action(int(row_id)),
            },
            edit_row_id=int(row_id),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self._reload_tags()
        self.refresh()

    def delete(self):
        row_id = self._selected_id()
        if row_id is None:
            show_info(self, tr("msg.info"), tr("msg.no_selection"))
            return
        r = self.table.currentRow()
        summary = f"{self.table.item(r,0).text()} | {self.table.item(r,1).text()} | {self.table.item(r,2).text()} | {self.table.item(r,3).text()}"
        if (
            QMessageBox.question(
                self,
                tr("msg.delete_entry"),
                trf("tracking.msg.delete_confirm", summary=summary),
            )
            != QMessageBox.Yes
        ):
            return
        try:
            self.model.delete(row_id)
        except SavingsGoalBoundsError as e:
            show_savings_goal_bounds_warning(self, e)
            return
        self.refresh()
