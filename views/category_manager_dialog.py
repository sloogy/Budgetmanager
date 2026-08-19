"""
Kategorien-Manager-Dialog für einfache Verwaltung aller Kategorien.

Features:
- Alle Kategorien auf einen Blick (gruppiert nach Typ)
- Schnelles Bearbeiten von Fixkosten, Wiederkehrend, Fälligkeitstag
- Mehrfachauswahl für Bulk-Operationen
- Direktes Erstellen/Umbenennen/Löschen
"""

from __future__ import annotations

from utils.accessibility import configure_dialog_tab_order
from utils.notifications import show_info, show_warning
import logging
import sqlite3

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from views.ui_colors import ui_colors
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QDialogButtonBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QWidget,
    QFrame,
    QSplitter,
    QMenu,
    QInputDialog,
    QHeaderView,
    QAbstractItemView,
    QSizePolicy,
)

from model.category_model import CategoryModel, Category
from model.category_forecast_mode import (
    FORECAST_MODE_AUTO,
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT,
)
from utils.icons import get_icon
from utils.i18n import tr, trf, display_typ, db_typ_from_display, tr_category_name
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from views.category_delete_dialog import ask_category_delete_decision


def _forecast_mode_label(mode: str) -> str:
    mode = str(mode or FORECAST_MODE_AUTO)
    if mode == FORECAST_MODE_POT:
        return tr("forecast.mode.pot")
    if mode == FORECAST_MODE_INCREMENTAL:
        return tr("forecast.mode.incremental")
    if mode == FORECAST_MODE_NORMAL:
        return tr("forecast.mode.normal")
    return tr("forecast.mode.auto")


class _CategoryTreeWidget(QTreeWidget):
    """Tree mit einfachem Drag & Drop für Kategorie-Ebenen.

    Drop-Ziele:
    - auf eine Kategorie: wird Unterkategorie dieser Kategorie
    - auf einen Typ-Header: wird Hauptkategorie dieses Typs
    """

    def __init__(self, owner: "CategoryManagerDialog"):
        super().__init__(owner)
        self._owner = owner

    def dropEvent(self, event):  # noqa: N802 (Qt naming)
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        current_item = self.currentItem()
        selected_items = [it for it in self.selectedItems() if it is not target_item]
        if (
            not selected_items
            and current_item is not None
            and current_item is not target_item
        ):
            selected_items = [current_item]
        if self._owner._handle_category_tree_drop(selected_items, target_item):
            event.acceptProposedAction()
            return
        event.ignore()


class CategoryManagerWidget(QWidget):
    """
    Umfassender Kategorien-Manager-Dialog.

    Ermöglicht schnelles und einfaches Verwalten aller Kategorien
    mit Mehrfachauswahl und Inline-Bearbeitung.
    """

    categories_changed = Signal()
    quick_add_requested = Signal()

    def __init__(
        self, parent=None, *, conn: sqlite3.Connection, embedded: bool = False
    ):
        # v2.2.16 (K8, Variante B): gemeinsamer Widget-Kern fuer den
        # Kategorie-Manager-Dialog UND die Sidebar-Seite. ``embedded`` blendet
        # den Schliessen-Button aus (auf einer Tab-Seite sinnlos).
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self._embedded = embedded
        self._build_ui()
        self._load_categories()

    def refresh(self) -> None:
        """Oeffentliche API fuer den Tab-Rahmen."""
        self._load_categories()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # === Toolbar ===
        toolbar = QHBoxLayout()

        self.btn_add = QPushButton(tr("btn.new_category"))
        self.btn_add.setIcon(get_icon("➕"))
        self.btn_add.clicked.connect(self._add_category)
        toolbar.addWidget(self.btn_add)

        self.btn_add_sub = QPushButton(tr("btn.subcategory"))
        self.btn_add_sub.setIcon(get_icon("📂"))
        self.btn_add_sub.clicked.connect(self._add_subcategory)
        toolbar.addWidget(self.btn_add_sub)

        toolbar.addSpacing(20)

        self.btn_rename = QPushButton(tr("ctx.rename"))
        self.btn_rename.setIcon(get_icon("✏️"))
        self.btn_rename.clicked.connect(self._rename_category)
        toolbar.addWidget(self.btn_rename)

        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_delete.setStyleSheet("")  # Theme handles button colors
        self.btn_delete.clicked.connect(self._delete_categories)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        # Filter
        toolbar.addWidget(QLabel(tr("lbl.filter_lbl")))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(tr("categories.filter_all"), "all")
        self.filter_combo.addItem(display_typ(TYP_EXPENSES), TYP_EXPENSES)
        self.filter_combo.addItem(display_typ(TYP_INCOME), TYP_INCOME)
        self.filter_combo.addItem(display_typ(TYP_SAVINGS), TYP_SAVINGS)
        self.filter_combo.addItem(tr("categories.filter_fixcosts"), "fix")
        self.filter_combo.addItem(tr("categories.filter_recurring"), "recurring")
        self.filter_combo.addItem(tr("forecast.mode.pot"), FORECAST_MODE_POT)
        self.filter_combo.addItem(
            tr("forecast.mode.incremental"), FORECAST_MODE_INCREMENTAL
        )
        self.filter_combo.currentIndexChanged.connect(lambda _idx: self._apply_filter())
        toolbar.addWidget(self.filter_combo)

        layout.addLayout(toolbar)

        drag_hint = QLabel(tr("catmgr.drag_hint"))
        drag_hint.setWordWrap(True)
        drag_hint.setMaximumHeight(44)
        drag_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        drag_hint.setStyleSheet("font-size: 12px;")
        layout.addWidget(drag_hint)

        # === Hauptbereich: Splitter mit Tree und Details ===
        splitter = QSplitter(Qt.Horizontal)

        # Kategorie-Baum
        self.tree = _CategoryTreeWidget(self)
        self.tree.setHeaderLabels(
            [
                tr("header.category"),
                tr("header.type"),
                tr("header.fix"),
                tr("header.recurring_short"),
                tr("header.day"),
                tr("forecast.mode.short"),
            ]
        )
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.viewport().setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setToolTip(tr("catmgr.drag_hint"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)

        # Spaltenbreiten
        # WICHTIG: QTreeWidget hat per Default stretchLastSection=True. Das
        # kollidiert mit "Spalte 0 = Stretch" (Kategorie-Spalte wird dann nicht
        # korrekt gedehnt -> Text abgeschnitten, toter Header-Raum rechts).
        # Daher zuerst abschalten, dann Spalte 0 als Füll-Spalte definieren.
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Kategorie füllt den Rest
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Typ
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Fix
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Wdh.
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Tag
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Forecast
        self.tree.setMinimumWidth(360)

        splitter.addWidget(self.tree)

        # Details-Panel
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)

        # Auswahl-Info
        self.selection_label = QLabel(tr("dlg.keine_auswahl"))
        self.selection_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        details_layout.addWidget(self.selection_label)

        # Eigenschaften-Editor
        props_group = QGroupBox(tr("lbl.edit_props"))
        props_layout = QGridLayout(props_group)

        # Fixkosten
        props_layout.addWidget(QLabel(tr("lbl.fixed_costs")), 0, 0)
        self.fix_combo = QComboBox()
        self.fix_combo.addItems(
            [
                tr("dlg.nicht_aendern"),
                tr("categories.activate"),
                tr("categories.deactivate"),
            ]
        )
        self.fix_combo.setToolTip(tr("help.tip.fixcost"))
        props_layout.addWidget(self.fix_combo, 0, 1)

        # Wiederkehrend
        props_layout.addWidget(QLabel(tr("lbl.recurring")), 1, 0)
        self.rec_combo = QComboBox()
        self.rec_combo.addItems(
            [
                tr("dlg.nicht_aendern"),
                tr("categories.activate"),
                tr("categories.deactivate"),
            ]
        )
        self.rec_combo.setToolTip(tr("help.tip.recurring"))
        props_layout.addWidget(self.rec_combo, 1, 1)

        # Fälligkeitstag
        props_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")), 2, 0)
        day_layout = QHBoxLayout()
        self.day_check = QCheckBox(tr("lbl.set_to"))
        self.day_combo = self._create_day_combo()
        self.day_combo.setToolTip(tr("help.tip.due_day"))
        self.day_combo.setEnabled(False)
        self.day_check.toggled.connect(self.day_combo.setEnabled)
        day_layout.addWidget(self.day_check)
        day_layout.addWidget(self.day_combo)
        day_layout.addStretch()
        props_layout.addLayout(day_layout, 2, 1)

        props_layout.addWidget(QLabel(tr("forecast.mode.label")), 3, 0)
        self.forecast_combo = QComboBox()
        # v2.2.0: zentrale Begriffshilfe direkt am Feld (Budgettopf etc.).
        self.forecast_combo.setToolTip(tr("help.budget_pot"))
        self.forecast_combo.addItem(tr("dlg.nicht_aendern"), None)
        self.forecast_combo.addItem(tr("forecast.mode.auto"), FORECAST_MODE_AUTO)
        self.forecast_combo.addItem(tr("forecast.mode.pot"), FORECAST_MODE_POT)
        self.forecast_combo.addItem(
            tr("forecast.mode.incremental"), FORECAST_MODE_INCREMENTAL
        )
        self.forecast_combo.addItem(tr("forecast.mode.normal"), FORECAST_MODE_NORMAL)
        self.forecast_combo.setToolTip(tr("forecast.mode.tooltip"))
        props_layout.addWidget(self.forecast_combo, 3, 1)

        # Anwenden-Button
        self.btn_apply = QPushButton(tr("dlg.aenderungen_anwenden_1"))
        self.btn_apply.setMinimumHeight(36)
        self.btn_apply.clicked.connect(self._apply_changes)
        self.btn_apply.setEnabled(False)
        props_layout.addWidget(self.btn_apply, 4, 0, 1, 2)

        details_layout.addWidget(props_group)

        # Schnellaktionen
        quick_group = QGroupBox(tr("lbl.quick_actions"))
        quick_layout = QVBoxLayout(quick_group)

        self.btn_all_fix = QPushButton(tr("ctx.bulk_fix_on"))
        self.btn_all_fix.setToolTip(tr("ctx.set_all_fix_on"))
        self.btn_all_fix.clicked.connect(lambda: self._quick_set_flag("is_fix", True))
        quick_layout.addWidget(self.btn_all_fix)

        self.btn_all_rec = QPushButton(tr("ctx.bulk_recurring_on"))
        self.btn_all_rec.setToolTip(tr("ctx.set_all_recurring_on"))
        self.btn_all_rec.clicked.connect(
            lambda: self._quick_set_flag("is_recurring", True)
        )
        quick_layout.addWidget(self.btn_all_rec)

        self.btn_no_fix = QPushButton(tr("ctx.bulk_fix_off"))
        self.btn_no_fix.setToolTip(tr("ctx.set_all_fix_off"))
        self.btn_no_fix.clicked.connect(lambda: self._quick_set_flag("is_fix", False))
        quick_layout.addWidget(self.btn_no_fix)

        self.btn_no_rec = QPushButton(tr("ctx.bulk_recurring_off"))
        self.btn_no_rec.setToolTip(tr("ctx.set_all_recurring_off"))
        self.btn_no_rec.clicked.connect(
            lambda: self._quick_set_flag("is_recurring", False)
        )
        quick_layout.addWidget(self.btn_no_rec)

        details_layout.addWidget(quick_group)
        details_layout.addStretch()

        details_widget.setMinimumWidth(280)
        splitter.addWidget(details_widget)
        # Beim Vergrößern soll der Kategorie-Baum den zusätzlichen Platz
        # bekommen, nicht das Detail-Panel. Panels dürfen nicht kollabieren.
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([600, 320])

        layout.addWidget(splitter, 1)

        # === Footer ===
        footer = QHBoxLayout()

        self.status_label = QLabel("")
        footer.addWidget(self.status_label)
        footer.addStretch()

        self.btn_refresh = QPushButton(tr("btn.refresh"))
        self.btn_refresh.setIcon(get_icon("🔄"))
        self.btn_refresh.clicked.connect(self._load_categories)
        footer.addWidget(self.btn_refresh)

        if not self._embedded:
            self.btn_close = QPushButton(tr("btn.close"))
            self.btn_close.clicked.connect(self._request_close)
            footer.addWidget(self.btn_close)

        layout.addLayout(footer)

    def _create_day_combo(self) -> QComboBox:
        """Dropdown für Fälligkeitstage: 1..28 + Monatsende."""
        combo = QComboBox()
        for day in range(1, 29):
            combo.addItem(trf("settings.day_of_month", day=day), day)
        combo.addItem(tr("settings.month_end"), 31)
        return combo

    def _set_day_combo_value(self, day: int) -> None:
        idx = self.day_combo.findData(max(1, min(31, int(day or 1))))
        if idx < 0:
            idx = self.day_combo.findData(1)
        self.day_combo.setCurrentIndex(max(0, idx))

    def _current_day_combo_value(self) -> int:
        try:
            return int(self.day_combo.currentData() or 1)
        except Exception:
            return 1

    def _load_categories(self) -> None:
        """Lädt alle Kategorien in den Baum."""
        self.tree.clear()

        c = ui_colors(self)
        type_colors = {
            TYP_EXPENSES: QColor(c.type_color(display_typ(TYP_EXPENSES))),
            TYP_INCOME: QColor(c.type_color(display_typ(TYP_INCOME))),
            TYP_SAVINGS: QColor(c.type_color(display_typ(TYP_SAVINGS))),
        }

        total_count = 0

        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
            cats = self.cat_model.list(typ)
            if not cats:
                continue

            # Typ als Root-Item
            type_item = QTreeWidgetItem(self.tree)
            type_item.setText(
                0,
                trf(
                    "categories.type_header_count",
                    typ=display_typ(typ),
                    count=len(cats),
                ),
            )
            type_item.setData(0, Qt.UserRole, {"type": "header", "typ": typ})
            type_item.setFlags(type_item.flags() | Qt.ItemIsDropEnabled)
            type_item.setExpanded(True)

            # Styling für Typ-Header
            font = type_item.font(0)
            font.setBold(True)
            type_item.setFont(0, font)
            type_item.setForeground(0, QBrush(type_colors.get(typ, QColor(c.text))))

            # Kategorien nach Parent gruppieren
            root_cats = [cat for cat in cats if not cat.parent_id]
            child_map = {}
            for cat in cats:
                if cat.parent_id:
                    if cat.parent_id not in child_map:
                        child_map[cat.parent_id] = []
                    child_map[cat.parent_id].append(cat)

            def add_category(cat: Category, parent_item: QTreeWidgetItem):
                item = QTreeWidgetItem(parent_item)
                display_name = tr_category_name(cat.name)
                item.setText(0, display_name)
                item.setText(1, display_typ(typ))
                item.setText(2, "✓" if cat.is_fix else "")
                item.setText(3, "✓" if cat.is_recurring else "")
                item.setText(4, str(cat.recurring_day) if cat.is_recurring else "")
                item.setText(
                    5,
                    _forecast_mode_label(
                        getattr(cat, "forecast_mode", FORECAST_MODE_AUTO)
                    ),
                )

                item.setFlags(
                    item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
                )
                item.setData(
                    0,
                    Qt.UserRole,
                    {
                        "type": "category",
                        "id": cat.id,
                        "name": cat.name,
                        "display_name": display_name,
                        "typ": typ,
                        "is_fix": cat.is_fix,
                        "is_recurring": cat.is_recurring,
                        "recurring_day": cat.recurring_day,
                        "forecast_mode": getattr(
                            cat, "forecast_mode", FORECAST_MODE_AUTO
                        ),
                        "parent_id": cat.parent_id,
                    },
                )

                # Farbkodierung
                if cat.is_fix and cat.is_recurring:
                    item.setBackground(
                        0, QBrush(QColor(c.warning_bg))
                    )  # Fix + Recurring
                elif cat.is_fix:
                    item.setBackground(0, QBrush(QColor(c.error_bg)))  # Nur Fix
                elif cat.is_recurring:
                    item.setBackground(0, QBrush(QColor(c.success_bg)))  # Nur Recurring

                # Kinder hinzufügen
                if cat.id in child_map:
                    for child in child_map[cat.id]:
                        add_category(child, item)

            for cat in root_cats:
                add_category(cat, type_item)
                total_count += 1

            # Kinder zählen
            total_count += len(cats) - len(root_cats)

        self.status_label.setText(trf("categories.loaded_count", count=total_count))
        self._apply_filter()

    def _apply_filter(self, _filter_text: str | None = None) -> None:
        """Wendet Filter auf die Kategorien an.

        Wichtig: Die Logik nutzt currentData(), nicht den übersetzten
        Anzeigetext. Dadurch funktionieren Sprachwechsel ohne kaputte Filter.
        """
        filter_value = (
            self.filter_combo.currentData() if hasattr(self, "filter_combo") else "all"
        )
        for i in range(self.tree.topLevelItemCount()):
            type_item = self.tree.topLevelItem(i)
            data = type_item.data(0, Qt.UserRole) or {}
            typ = data.get("typ", "")

            show_type = (
                filter_value == "all"
                or filter_value == typ
                or filter_value
                in ("fix", "recurring", FORECAST_MODE_POT, FORECAST_MODE_INCREMENTAL)
            )
            type_item.setHidden(not show_type)

            if show_type:
                visible_children = 0
                for j in range(type_item.childCount()):
                    child = type_item.child(j)
                    child_data = child.data(0, Qt.UserRole) or {}

                    show_child = True
                    if filter_value == "fix":
                        show_child = child_data.get("is_fix", False)
                    elif filter_value == "recurring":
                        show_child = child_data.get("is_recurring", False)
                    elif filter_value in (FORECAST_MODE_POT, FORECAST_MODE_INCREMENTAL):
                        show_child = (
                            child_data.get("forecast_mode", FORECAST_MODE_AUTO)
                            == filter_value
                        )

                    child.setHidden(not show_child)
                    if show_child:
                        visible_children += 1

                if (
                    filter_value
                    in (
                        "fix",
                        "recurring",
                        FORECAST_MODE_POT,
                        FORECAST_MODE_INCREMENTAL,
                    )
                    and visible_children == 0
                ):
                    type_item.setHidden(True)

    def _get_selected_categories(self) -> list[dict]:
        """Gibt die ausgewählten Kategorien zurück."""
        selected = []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data.get("type") == "category":
                selected.append(data)
        return selected

    def _on_selection_changed(self) -> None:
        """Reagiert auf Auswahl-Änderungen."""
        selected = self._get_selected_categories()
        count = len(selected)

        if count == 0:
            self.selection_label.setText(tr("dlg.keine_auswahl"))
            self.btn_apply.setEnabled(False)
        elif count == 1:
            cat = selected[0]
            self.selection_label.setText(
                trf(
                    "lbl.selected_category",
                    name=cat.get("display_name", cat["name"]),
                    typ=display_typ(cat["typ"]),
                )
            )
            self.btn_apply.setEnabled(True)

            # Felder vorbelegen
            self.fix_combo.setCurrentIndex(1 if cat["is_fix"] else 2)
            self.rec_combo.setCurrentIndex(1 if cat["is_recurring"] else 2)
            if cat["is_recurring"]:
                self.day_check.setChecked(True)
                self._set_day_combo_value(cat["recurring_day"])
            else:
                self.day_check.setChecked(False)
            idx = self.forecast_combo.findData(
                cat.get("forecast_mode", FORECAST_MODE_AUTO)
            )
            self.forecast_combo.setCurrentIndex(idx if idx >= 0 else 1)
        else:
            self.selection_label.setText(
                trf("dlg.count_kategorien_ausgewaehlt", count=count)
            )
            self.btn_apply.setEnabled(True)
            # Reset Combos für Mehrfachauswahl
            self.fix_combo.setCurrentIndex(0)
            self.rec_combo.setCurrentIndex(0)
            self.day_check.setChecked(False)
            self.forecast_combo.setCurrentIndex(0)

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Doppelklick öffnet Umbenennen."""
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "category":
            self._rename_category()

    def _show_context_menu(self, pos) -> None:
        """Zeigt Kontextmenü."""
        item = self.tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.UserRole)
        if not data or data.get("type") != "category":
            return

        menu = QMenu(self)
        cat = data

        act_rename = menu.addAction(tr("ctx.rename"), self._rename_category)
        act_rename.setIcon(get_icon("✏️"))
        menu.addAction(tr("btn.unterkategorie_hinzufuegen"), self._add_subcategory)
        menu.addSeparator()

        # Alternative zum Drag & Drop: Ebenen gezielt per Kontextmenü wechseln.
        self._build_move_menu(menu, cat)
        menu.addSeparator()

        fix_text = (
            tr("budget.ctx.fix_disable")
            if cat["is_fix"]
            else tr("budget.ctx.fix_enable")
        )
        menu.addAction(
            fix_text,
            lambda: self._toggle_single_flag(cat["id"], "is_fix", not cat["is_fix"]),
        )

        rec_text = (
            tr("budget.ctx.rec_disable")
            if cat["is_recurring"]
            else tr("budget.ctx.rec_enable")
        )
        menu.addAction(
            rec_text,
            lambda: self._toggle_single_flag(
                cat["id"], "is_recurring", not cat["is_recurring"]
            ),
        )

        act_set_day = menu.addAction(
            trf("categories.set_due_day_action", day=cat["recurring_day"]),
            lambda: self._set_single_day(cat["id"]),
        )
        act_set_day.setIcon(get_icon("📅"))

        menu.addSeparator()
        mode_menu = menu.addMenu(tr("forecast.mode.label"))
        mode_menu.addAction(
            tr("forecast.mode.auto"),
            lambda: self._toggle_single_flag(
                cat["id"], "forecast_mode", FORECAST_MODE_AUTO
            ),
        )
        mode_menu.addAction(
            tr("forecast.mode.pot"),
            lambda: self._toggle_single_flag(
                cat["id"], "forecast_mode", FORECAST_MODE_POT
            ),
        )
        mode_menu.addAction(
            tr("forecast.mode.incremental"),
            lambda: self._toggle_single_flag(
                cat["id"], "forecast_mode", FORECAST_MODE_INCREMENTAL
            ),
        )
        mode_menu.addAction(
            tr("forecast.mode.normal"),
            lambda: self._toggle_single_flag(
                cat["id"], "forecast_mode", FORECAST_MODE_NORMAL
            ),
        )

        menu.addSeparator()
        menu.addAction(tr("btn.loeschen_1"), self._delete_categories)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _is_descendant_id(
        self, typ: str, parent_id: int, possible_child_id: int
    ) -> bool:
        """True, wenn possible_child_id irgendwo unter parent_id hängt."""
        all_cats = self.cat_model.list(typ)
        child_map: dict[int, list[int]] = {}
        for cat in all_cats:
            if cat.parent_id is not None:
                child_map.setdefault(int(cat.parent_id), []).append(int(cat.id))

        stack = list(child_map.get(int(parent_id), []))
        seen: set[int] = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            if cur == int(possible_child_id):
                return True
            seen.add(cur)
            stack.extend(child_map.get(cur, []))
        return False

    def _handle_category_tree_drop(
        self, dragged_items: list[QTreeWidgetItem], target_item: QTreeWidgetItem | None
    ) -> bool:
        """Verschiebt Kategorien per Drag & Drop auf eine neue Ebene."""
        if target_item is None:
            return False

        target_data = target_item.data(0, Qt.UserRole) or {}
        if target_data.get("type") == "header":
            target_typ = target_data.get("typ")
            new_parent_id = None
            target_label = display_typ(target_typ)
        elif target_data.get("type") == "category":
            target_typ = target_data.get("typ")
            new_parent_id = int(target_data.get("id"))
            target_label = target_data.get("display_name", target_data.get("name", ""))
        else:
            return False

        dragged_data = []
        seen_ids: set[int] = set()
        for item in dragged_items:
            data = item.data(0, Qt.UserRole) or {}
            if data.get("type") != "category":
                continue
            cat_id = int(data.get("id"))
            if cat_id not in seen_ids:
                dragged_data.append(data)
                seen_ids.add(cat_id)

        if not dragged_data:
            return False

        for cat in dragged_data:
            cat_id = int(cat["id"])
            if cat.get("typ") != target_typ:
                show_warning(
                    self, tr("dlg.hinweis"), tr("categories.drag_only_same_type")
                )
                return False
            if new_parent_id == cat_id:
                show_warning(
                    self, tr("dlg.hinweis"), tr("categories.drag_not_onto_self")
                )
                return False
            if new_parent_id is not None and self._is_descendant_id(
                cat["typ"], cat_id, new_parent_id
            ):
                show_warning(self, tr("dlg.hinweis"), tr("categories.drag_no_cycle"))
                return False

        changed = 0
        try:
            for cat in dragged_data:
                current_parent_id = cat.get("parent_id")
                if current_parent_id == new_parent_id:
                    continue
                self.cat_model.update_parent(int(cat["id"]), new_parent_id)
                changed += 1
        except Exception as e:
            reason = str(e)
            msg = (
                tr(reason)
                if reason.startswith("catmgr.")
                else trf("categories.move_failed", e=e)
            )
            QMessageBox.critical(self, tr("msg.error"), msg)
            return False

        if changed:
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(
                trf("categories.moved_count", count=changed, target=target_label)
            )
        return bool(changed)

    def _reparent(self, cat_id: int, new_parent_id: int | None) -> None:
        """Gemeinsame Logik für Kontextmenü und gezielte Ebenenwechsel."""
        current = self.cat_model.get_by_id(cat_id)
        if current is not None and current.parent_id == new_parent_id:
            return

        ok, reason = self.cat_model.can_reparent(cat_id, new_parent_id)
        if not ok:
            show_warning(self, tr("catmgr.move_not_possible"), tr(reason))
            return

        try:
            self.cat_model.update_parent(cat_id, new_parent_id)
            self._load_categories()
            self.categories_changed.emit()
            self._select_category_by_id(cat_id)
        except Exception as e:
            reason = str(e)
            msg = (
                tr(reason)
                if reason.startswith("catmgr.")
                else trf("categories.move_failed", e=e)
            )
            QMessageBox.critical(self, tr("msg.error"), msg)

    def _select_category_by_id(self, cat_id: int) -> None:
        """Sucht das Tree-Item zur ID, selektiert es und scrollt dorthin."""

        def walk(item: QTreeWidgetItem) -> bool:
            for i in range(item.childCount()):
                child = item.child(i)
                data = child.data(0, Qt.UserRole) or {}
                if data.get("type") == "category" and int(data.get("id", -1)) == int(
                    cat_id
                ):
                    self.tree.setCurrentItem(child)
                    self.tree.scrollToItem(child)
                    return True
                if walk(child):
                    return True
            return False

        for i in range(self.tree.topLevelItemCount()):
            if walk(self.tree.topLevelItem(i)):
                break

    def _promote_to_top(self, cat_id: int) -> None:
        """Macht eine Unterkategorie zur Hauptkategorie."""
        self._reparent(cat_id, None)

    def _build_move_menu(self, menu: QMenu, cat: dict) -> None:
        """Baut das Untermenü 'Verschieben unter…' mit gültigen Parent-Zielen."""
        move_menu = menu.addMenu(tr("catmgr.move_under"))
        move_menu.setIcon(get_icon("📦"))

        cat_id = int(cat["id"])
        typ = cat["typ"]
        invalid = self.cat_model._descendant_ids(cat_id) | {cat_id}

        if cat.get("parent_id"):
            act_top = move_menu.addAction(tr("catmgr.move_to_top"))
            act_top.setIcon(get_icon("⬆️"))
            act_top.triggered.connect(
                lambda _=False, cid=cat_id: self._promote_to_top(cid)
            )
            move_menu.addSeparator()

        candidates = [c for c in self.cat_model.list(typ) if c.id not in invalid]
        if not candidates:
            act_none = move_menu.addAction(tr("catmgr.move_no_targets"))
            act_none.setEnabled(False)
            return

        for c in candidates:
            label = self.cat_model.display_with_parent(typ, c.name)
            act = move_menu.addAction(label)
            act.triggered.connect(
                lambda _=False, cid=cat_id, pid=int(c.id): self._reparent(cid, pid)
            )

    def _make_root_category(self, cat: dict) -> None:
        """Macht eine Kategorie wieder zur Hauptkategorie."""
        self._reparent(int(cat["id"]), None)

    def _toggle_single_flag(self, cat_id: int, flag: str, value: bool) -> None:
        """Schaltet ein einzelnes Flag um."""
        try:
            self.cat_model.update_flags(cat_id, **{flag: value})
            self._load_categories()
            self.categories_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))

    def _set_single_day(self, cat_id: int) -> None:
        """Setzt den Fälligkeitstag für eine einzelne Kategorie."""
        items = [(trf("settings.day_of_month", day=d), d) for d in range(1, 29)]
        items.append((tr("settings.month_end"), 31))
        text, ok = QInputDialog.getItem(
            self,
            tr("dlg.faelligkeitstag"),
            tr("categories.day_prompt"),
            [label for label, _day in items],
            0,
            False,
        )
        if ok:
            day = next((_day for label, _day in items if label == text), 1)
            try:
                self.cat_model.update_flags(
                    cat_id, is_recurring=True, recurring_day=day
                )
                self._load_categories()
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.critical(
                    self, tr("msg.error"), trf("msg.change_failed", e=e)
                )

    def _apply_changes(self) -> None:
        """Wendet die Änderungen auf alle ausgewählten Kategorien an."""
        selected = self._get_selected_categories()
        if not selected:
            return

        fix_choice = self.fix_combo.currentIndex()
        rec_choice = self.rec_combo.currentIndex()
        set_day = self.day_check.isChecked()
        day_val = self._current_day_combo_value()
        forecast_choice = self.forecast_combo.currentData()

        if (
            fix_choice == 0
            and rec_choice == 0
            and not set_day
            and forecast_choice is None
        ):
            show_info(self, tr("msg.info"), tr("msg.no_changes_selected"))
            return

        changed = 0
        errors = []

        for cat in selected:
            try:
                kwargs = {}

                if fix_choice == 1:
                    kwargs["is_fix"] = True
                elif fix_choice == 2:
                    kwargs["is_fix"] = False

                if rec_choice == 1:
                    kwargs["is_recurring"] = True
                elif rec_choice == 2:
                    kwargs["is_recurring"] = False

                if set_day:
                    kwargs["is_recurring"] = True
                    kwargs["recurring_day"] = day_val
                if forecast_choice is not None:
                    kwargs["forecast_mode"] = str(forecast_choice)

                if kwargs:
                    self.cat_model.update_flags(cat["id"], **kwargs)
                    changed += 1

            except Exception as e:
                errors.append(f"{cat.get('display_name', cat['name'])}: {e}")

        if changed > 0:
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(trf("categories.updated_count", count=changed))

        if errors:
            show_warning(
                self,
                tr("categories.partial_failed_title"),
                tr("categories.errors_at") + "\n" + "\n".join(errors[:10]),
            )

    def _quick_set_flag(self, flag: str, value: bool) -> None:
        """Setzt ein Flag für alle ausgewählten Kategorien."""
        selected = self._get_selected_categories()
        if not selected:
            show_info(self, tr("msg.info"), tr("msg.no_categories_selected"))
            return

        changed = 0
        for cat in selected:
            try:
                self.cat_model.update_flags(cat["id"], **{flag: value})
                changed += 1
            except Exception as e:
                logger.debug(
                    "self.cat_model.update_flags(cat['id'], **{flag: va: %s", e
                )

        if changed > 0:
            self._load_categories()
            self.categories_changed.emit()
            if flag == "is_fix":
                flag_name = tr("tracking.title.fixcosts")
                status = (
                    tr("categories.status_activated")
                    if value
                    else tr("categories.status_deactivated")
                )
            elif flag == "is_recurring":
                flag_name = tr("lbl.recurring")
                status = (
                    tr("categories.status_activated")
                    if value
                    else tr("categories.status_deactivated")
                )
            else:
                flag_name = tr("forecast.mode.label")
                status = _forecast_mode_label(str(value))
            self.status_label.setText(
                trf(
                    "dlg.flag_name_fuer_changed_kategorien",
                    flag_name=flag_name,
                    changed=changed,
                    status=status,
                )
            )

    def _add_category(self) -> None:
        """Fügt eine neue Kategorie hinzu."""
        # Typ auswählen
        typ_options = [
            (display_typ(TYP_EXPENSES), TYP_EXPENSES),
            (display_typ(TYP_INCOME), TYP_INCOME),
            (display_typ(TYP_SAVINGS), TYP_SAVINGS),
        ]
        typ_display, ok = QInputDialog.getItem(
            self,
            tr("budget.ctx.new_category"),
            tr("header.type"),
            [label for label, _typ in typ_options],
            0,
            False,
        )
        if not ok:
            return
        typ = next(
            (_typ for label, _typ in typ_options if label == typ_display), TYP_EXPENSES
        )

        name, ok = QInputDialog.getText(
            self,
            tr("budget.ctx.new_category"),
            trf("categories.new_category_name_prompt", typ=display_typ(typ)),
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        # Prüfen ob existiert
        for cat in self.cat_model.list(typ):
            if cat.name.lower() == name.lower():
                show_warning(
                    self, tr("msg.error"), trf("categories.category_exists", name=name)
                )
                return

        try:
            self.cat_model.create(typ=typ, name=name)
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(trf("categories.created", name=name))
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), trf("categories.create_failed", e=e)
            )

    def _add_subcategory(self) -> None:
        """Fügt eine Unterkategorie zur ausgewählten Kategorie hinzu."""
        selected = self._get_selected_categories()
        if len(selected) != 1:
            show_info(
                self, tr("dlg.hinweis"), tr("categories.select_exactly_one_parent")
            )
            return

        parent = selected[0]

        name, ok = QInputDialog.getText(
            self,
            tr("budget.title.new_subcategory"),
            trf(
                "categories.new_subcategory_name_prompt",
                parent=parent.get("display_name", parent["name"]),
            ),
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        try:
            self.cat_model.create(typ=parent["typ"], name=name, parent_id=parent["id"])
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(trf("categories.subcategory_created", name=name))
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), trf("categories.create_failed", e=e)
            )

    def _rename_category(self) -> None:
        """Benennt die ausgewählte Kategorie um."""
        selected = self._get_selected_categories()
        if len(selected) != 1:
            show_info(
                self, tr("dlg.hinweis"), tr("categories.select_exactly_one_rename")
            )
            return

        cat = selected[0]

        new_name, ok = QInputDialog.getText(
            self,
            tr("budget.title.rename_category"),
            trf("categories.rename_prompt", name=cat.get("display_name", cat["name"])),
            text=cat["name"],
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        if new_name == cat["name"]:
            return

        # Prüfen ob existiert
        for c in self.cat_model.list(cat["typ"]):
            if c.name.lower() == new_name.lower() and c.id != cat["id"]:
                show_warning(
                    self,
                    tr("msg.error"),
                    trf("categories.category_exists", name=new_name),
                )
                return

        try:
            self.cat_model.rename_and_cascade(
                cat["id"], typ=cat["typ"], old_name=cat["name"], new_name=new_name
            )
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(
                trf("categories.renamed", old=cat["name"], new=new_name)
            )
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), trf("categories.rename_failed", e=e)
            )

    def _delete_categories(self) -> None:
        """Löscht die ausgewählten Kategorien."""
        selected = self._get_selected_categories()
        if not selected:
            show_info(self, tr("msg.info"), tr("msg.no_categories_selected"))
            return

        ids = sorted({int(c["id"]) for c in selected})
        decision = ask_category_delete_decision(self, conn=self.conn, cat_ids=ids)
        if decision is None:
            return

        try:
            result = self.cat_model.delete_categories_safely(
                ids,
                data_action=decision.action,
                reassign_to_id=decision.reassign_to_id,
                promote_children=True,
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.delete_failed", e=e))
            return

        deleted = int(result.get("deleted", 0) or 0)
        if deleted > 0:
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(
                trf("dlg.deleted_kategorien_geloescht", deleted=deleted)
            )

    def _request_close(self) -> None:
        """Schliesst das umgebende Fenster (Dialog), No-op im eingebetteten Tab."""
        w = self.window()
        if w is not None and w is not self:
            w.close()


class CategoryManagerDialog(QDialog):
    """Duenne Dialog-Huelle um den gemeinsamen CategoryManagerWidget (K8-B)."""

    categories_changed = Signal()

    def __init__(self, parent=None, *, conn: sqlite3.Connection):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.category_manager"))
        self.setModal(False)
        self.setMinimumSize(900, 600)
        from utils.responsive_dialog import harden_dialog_for_screen

        harden_dialog_for_screen(self)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.core = CategoryManagerWidget(self, conn=conn, embedded=False)
        self.core.categories_changed.connect(self.categories_changed.emit)
        lay.addWidget(self.core)
        configure_dialog_tab_order(self)

    def _load_categories(self):
        # Kompatibilitaet fuer bestehende Aufrufer/Tests.
        self.core._load_categories()


class CategoriesTab(QWidget):
    """Sidebar-Seite: bettet denselben CategoryManagerWidget ein (K8-B)."""

    quick_add_requested = Signal()
    categories_changed = Signal()

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.core = CategoryManagerWidget(self, conn=conn, embedded=True)
        self.core.categories_changed.connect(self.categories_changed.emit)
        self.core.quick_add_requested.connect(self.quick_add_requested.emit)
        lay.addWidget(self.core)

    def refresh(self) -> None:
        self.core.refresh()

    # Durchreichen der von main_window genutzten Aktionen:
    def add_root_category(self) -> None:
        self.core._add_category()

    def add_subcategory(self) -> None:
        self.core._add_subcategory()

    def delete_selected(self) -> None:
        self.core._delete_categories()

    def mass_edit(self) -> None:
        # Der Kern bearbeitet Mehrfachauswahl inline im Eigenschaften-Panel;
        # ein separater Mass-Edit-Dialog entfaellt. Fokus auf den Baum genuegt.
        try:
            self.core.tree.setFocus()
        except Exception:
            pass
