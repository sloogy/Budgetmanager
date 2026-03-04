from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3

from PySide6.QtCore import Qt, QEvent, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    QMenu, QInputDialog
)

from utils.i18n import tr, trf
from utils.icons import get_icon
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
from utils.i18n import display_typ, db_typ_from_display, tr_category_name
from model.category_model import CategoryModel, Category
from model.budget_model import BudgetModel
from model.favorites_model import FavoritesModel
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from views.copy_year_dialog import CopyYearDialog
from views.budget_entry_dialog import BudgetEntryDialog, BudgetEntryRequest
# Erweiterter Dialog mit integrierter Kategorie-Verwaltung
from views.budget_entry_dialog_extended import BudgetEntryDialogExtended
# Kategorie-Eigenschaften-Dialoge
from views.category_properties_dialog import (
    CategoryPropertiesDialog, 
    BulkCategoryEditDialog,
    QuickCategoryDialog
)

def _months() -> list[str]: return [tr(f"month_short.{i}") for i in range(1, 13)]
# UserRole keys
ROLE_CAT_REAL = Qt.UserRole + 1     # str
ROLE_DEPTH = Qt.UserRole + 2        # int
ROLE_HAS_CHILDREN = Qt.UserRole + 3 # bool
ROLE_PATH = Qt.UserRole + 4         # str
ROLE_COLLAPSED = Qt.UserRole + 5     # bool (für Baum-Zuklappen)
ROLE_TYP = Qt.UserRole + 10         # str (bereits im alten Code genutzt)


from utils.money import parse_money
from views.ui_colors import ui_colors

def parse_amount(text: str) -> float:
    return parse_money(text)


def fmt_amount(val: float) -> str:
    if abs(val) < 1e-9:
        return "0.00"
    return f"{val:.2f}"


def _parse_cell_amount(text: str) -> float:
    """Parst eine Betrags-Zelle, auch im Format 'Kinder + Puffer' oder '1600.00+'."""
    raw = (text or "").strip().rstrip("+").strip()
    if " + " in raw:
        return sum(parse_amount(p) for p in raw.split(" + "))
    return parse_amount(raw)



class BudgetTab(QWidget):
    """Budget-Tab mit Tree-Ansicht.

    Regeln:
    - Leaf-Kategorien: editierbar (Monate + Total)
    - Parent mit Children: Monatszellen read-only.
      Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
    - Parent ohne Children: wie Leaf (normales Budgetverhalten)

    Footer (TOTAL): zählt **Leaf-Werte + Parent-Puffer** (keine Doppelzählung).
    """
    
    # Signal für Schnelleingabe (wird von MainWindow abgehört)
    quick_add_requested = Signal()
    # Signal: Budget-Daten wurden gespeichert (autosave oder manuell)
    budget_data_changed = Signal()

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.cats = CategoryModel(conn)
        self.budget = BudgetModel(conn)
        self.favorites = FavoritesModel(conn)
        self.warnings = BudgetWarningsModelExtended(conn)

        self._internal_change = False

        # Cache: (typ, cat) -> {month:int -> buffer(float)}
        self._buffer_cache: dict[tuple[str, str], dict[int, float]] = {}

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(2024)

        self.typ_cb = QComboBox()
        for _disp, _key in [(tr("typ.Alle"), ""), (tr("typ.Ausgaben"), "Ausgaben"),
                           (tr("typ.Einkommen"), "Einkommen"), (tr("typ.Ersparnisse"), "Ersparnisse")]:
            self.typ_cb.addItem(_disp, _key)

        # Baum-Ansicht (Ein-/Ausblenden / Ebenen)
        self.btn_tree = QPushButton(tr("budget.btn.tree"))
        self.btn_tree.setToolTip(tr("budget.tip.tree"))

        # Baum-Ansicht: 'tree' (Einrueckung/Marker) oder 'path' (Pfadtext)
        self._tree_view_mode = 'tree'

        # Typ-Farben (aus Theme-Profil, fallback Default)
        self._type_colors = self._get_type_color_map()


        self.btn_load = QPushButton(tr("budget.btn.load"))
        self.btn_save = QPushButton(tr("btn.save"))
        self.btn_seed = QPushButton(tr("budget.btn.seed"))
        self.btn_copy = QPushButton(tr("budget.btn.copy_year"))

        self.btn_entry = QPushButton(tr("budget.btn.entry"))
        self.btn_edit = QPushButton(tr("budget.btn.edit"))
        
        # Schnelleingabe-Button
        self.btn_quick_add = QPushButton(tr("budget.btn.quick_add"))
        self.btn_quick_add.setToolTip(tr("budget.tip.quick_add"))

        self.btn_remove_budgetrow = QPushButton(tr("budget.btn.remove_row"))
        self.btn_remove_category = QPushButton(tr("budget.btn.delete_category_global"))

        self.chk_autosave = QCheckBox(tr("chk.autosave"))
        self.chk_autosave.setChecked(False)

        self.chk_ask_due = QCheckBox(tr("budget.chk.ask_due"))
        self.chk_ask_due.setChecked(False)

        # Kleine Übersicht (oberhalb der Tabelle)
        self.lbl_overview = QLabel("")
        self.lbl_overview.setToolTip(tr("budget.tip.overview"))

        # Bezeichnung + Fix + Wiederh. + Tag + 12 Monate + Total
        self.table = QTableWidget(0, 17)
        self.table.setHorizontalHeaderLabels([tr("header.designation"), tr("header.fix"), tr("header.recurring_symbol"), tr("header.day")] + _months() + [tr("header.total")])
        
        # Spaltenbreiten optimieren
        self.table.setColumnWidth(0, 280)  # Bezeichnung
        self.table.setColumnWidth(1, 35)   # Fix
        self.table.setColumnWidth(2, 35)   # Wiederh.
        self.table.setColumnWidth(3, 45)   # Tag
        
        # Spaltenbreiten optimieren
        self.table.setColumnWidth(0, 280)  # Bezeichnung breiter für Hierarchie
        self.table.setColumnWidth(1, 35)   # Fix-Stern (schmal)
        self.table.setColumnWidth(2, 35)   # Wiederh-Symbol (schmal)
        self.table.setColumnWidth(3, 45)   # Tag (schmal)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)

        # Events
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)  # NEU: Fix/Wiederkehrend Toggle
        # Defer installEventFilter until after Qt event loop starts to avoid
        # "Cannot filter events for objects in a different thread" warning
        QTimer.singleShot(0, lambda: self.table.installEventFilter(self))
        
        # Rechtsklick-Kontextmenü
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Shortcuts
        self.sc_save = QShortcut(QKeySequence.Save, self)
        self.sc_save.activated.connect(self.save)

        # Kompakte Top-Leiste
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("lbl.year")))
        top.addWidget(self.year_spin)
        top.addWidget(QLabel(tr("lbl.type")))
        top.addWidget(self.typ_cb)
        top.addWidget(self.btn_tree)
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_save)
        top.addWidget(self.chk_autosave)
        top.addStretch(1)
        top.addWidget(self.btn_quick_add)  # Schnelleingabe
        top.addWidget(self.btn_entry)  # Budget erfassen
        top.addWidget(self.btn_edit)   # Budget bearbeiten
        top.addWidget(self.btn_remove_category)  # Kategorie löschen
        
        # Versteckte Buttons für Menü-Zugriff
        self.btn_seed.setVisible(False)
        self.btn_copy.setVisible(False)
        self.btn_remove_budgetrow.setVisible(False)
        self.chk_ask_due.setVisible(False)

        root = QVBoxLayout()
        root.addLayout(top)

        summary = QHBoxLayout()
        summary.addWidget(self.lbl_overview)
        summary.addStretch(1)
        root.addLayout(summary)

        root.addWidget(self.table)
        self.setLayout(root)

        self.btn_load.clicked.connect(self.load)
        self.btn_save.clicked.connect(self.save)
        self.btn_tree.clicked.connect(self._show_tree_menu)
        self.btn_copy.clicked.connect(self.copy_year_dialog)
        self.btn_seed.clicked.connect(self.seed_from_categories)
        self.typ_cb.currentTextChanged.connect(lambda _: self.load())
        self.btn_entry.clicked.connect(self.open_entry_dialog)
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        self.btn_remove_budgetrow.clicked.connect(self.remove_budget_row)
        self.btn_remove_category.clicked.connect(self.delete_category_global)
        self.btn_quick_add.clicked.connect(self.quick_add_requested.emit)

        self.load()

    # --- i18n helper: Typ aus ComboBox (Anzeige -> DB) ---
    def _current_typ_db(self) -> str:
        data = self.typ_cb.currentData()
        if data is not None:
            return data if data else "Alle"
        return "Alle"

    def _is_all_filter(self) -> bool:
        return self._current_typ_db() == "Alle"

    # --- Komfort: Enter -> nächste Zelle ---
    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r < 0 or c < 0:
                    return False
                # Spalten: 0=Bezeichnung, 1=Fix, 2=∞, 3=Tag, 4-15=Monate, 16=Total
                if c < 4:
                    # Von Bezeichnung/Fix/∞/Tag -> erste Monatsspalte
                    # QTimer.singleShot: verhindert Segfault durch Qt-Reentrancy
                    # (setCurrentCell innerhalb von eventFilter → commitData → installEventFilter → eventFilter)
                    QTimer.singleShot(0, lambda: self.table.setCurrentCell(r, 4))
                else:
                    next_c = c + 1
                    next_r = r
                    if next_c > 16:  # nach Total -> nächste Zeile
                        next_c = 4  # Zurück zur ersten Monatsspalte
                        next_r = r + 1
                    if next_r >= self.table.rowCount():
                        next_r = self.table.rowCount() - 1
                    QTimer.singleShot(0, lambda: self.table.setCurrentCell(next_r, next_c))
                return True
        return super().eventFilter(obj, event)

    # -----------------------------
    # Helpers: Row meta
    # -----------------------------
    def _is_footer_row(self, r: int) -> bool:
        it = self.table.item(r, 0)
        return bool(it and it.text() == "TOTAL")

    def _is_header_row(self, r: int) -> bool:
        it = self.table.item(r, 0)
        if not it:
            return False
        return (it.data(ROLE_CAT_REAL) is None) and it.text().startswith("═══")

    def _row_count_data(self) -> int:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text() == "TOTAL":
                return r
        return self.table.rowCount()

    def _row_typ(self, r: int) -> str:
        it0 = self.table.item(r, 0)
        if it0:
            t = it0.data(ROLE_TYP)
            if t:
                return str(t)
        # fallback
        return TYP_EXPENSES if self._is_all_filter() else self._current_typ_db()


    def _get_type_color_map(self) -> dict[str, QColor]:
        """Lädt Farben für Einnahmen/Ausgaben/Ersparnisse aus dem aktuellen Theme-Profil.
        Fallback via ui_colors.
        """
        _uc = ui_colors(self)
        defaults = _uc.type_colors
        try:
            # ThemeManager vom MainWindow holen (keine neue Instanz!)
            main_window = self.window()
            if hasattr(main_window, 'theme_manager'):
                m = main_window.theme_manager.get_type_colors()
                return {k: QColor(v) for k, v in (m or defaults).items()}
        except Exception as e:
            logger.debug("main_window = self.window(): %s", e)
        return {k: QColor(v) for k, v in defaults.items()}

    def _typ_color(self, typ: str) -> QColor:
        """Gibt eine Farbe für den jeweiligen Typ zurück."""
        m = getattr(self, "_type_colors", None) or {}
        if typ in m:
            return m[typ]
        # Fallback auf normalisiertem DB-Key
        from model.typ_constants import normalize_typ as _nt
        if _nt(typ) == "Einkommen" and "Einkommen" in m:
            return m["Einkommen"]
        return QColor(ui_colors(self).neutral)

    def _row_cat_real(self, r: int) -> str | None:
        it0 = self.table.item(r, 0)
        if not it0:
            return None
        v = it0.data(ROLE_CAT_REAL)
        if v:
            return str(v)
        return None

    def _row_depth(self, r: int) -> int:
        it0 = self.table.item(r, 0)
        if not it0:
            return -1
        d = it0.data(ROLE_DEPTH)
        return int(d) if d is not None else -1

    def _row_has_children(self, r: int) -> bool:
        it0 = self.table.item(r, 0)
        if not it0:
            return False
        v = it0.data(ROLE_HAS_CHILDREN)
        return bool(v)

    # -----------------------------
    # Tree build + totals
    # -----------------------------
    def _build_tree_flat(self, typ: str, matrix: dict[str, dict[int, float]]):
        """Returns flattened rows with computed totals.

        Returns:
          flat: list[dict] with keys:
            name, depth, has_children, path
          totals_by_name: dict[name][month] -> total (buffer + subtree)
          buffer_by_name: dict[name][month] -> own buffer (DB value)
        """
        items = self.cats.list(typ)
        nodes = self.cats.build_tree(items)

        # id->name for path
        by_id: dict[int, Category] = {c.id: c for c in items}

        totals_by_name: dict[str, dict[int, float]] = {}
        buffer_by_name: dict[str, dict[int, float]] = {}
        has_children_name: dict[str, bool] = {}
        direct_children_by_name: dict[str, list[str]] = {}

        def compute(node) -> dict[int, float]:
            c: Category = node["cat"]
            own = {m: float(matrix.get(c.name, {}).get(m, 0.0)) for m in range(1, 13)}
            total = dict(own)
            for ch in node["children"]:
                ct = compute(ch)
                for m in range(1, 13):
                    total[m] = float(total.get(m, 0.0)) + float(ct.get(m, 0.0))
            totals_by_name[c.name] = total
            buffer_by_name[c.name] = own
            has_children_name[c.name] = bool(node["children"])
            direct_children_by_name[c.name] = [ch["cat"].name for ch in node["children"]]
            return total

        for n in nodes:
            compute(n)

        flat: list[dict] = []

        def walk(children, depth: int, path_parts: list[str]):
            for n in children:
                c: Category = n["cat"]
                cur_path = path_parts + [c.name]
                flat.append(
                    {
                        "name": c.name,
                        "depth": depth,
                        "has_children": bool(n["children"]),
                        "path": " › ".join(cur_path),
                        "is_fix": bool(c.is_fix),
                        "is_recurring": bool(c.is_recurring),
                        "recurring_day": int(c.recurring_day or 1),
                    }
                )
                walk(n["children"], depth + 1, cur_path)

        walk(nodes, 0, [])
        return flat, totals_by_name, buffer_by_name, direct_children_by_name


    # ═══════════════════════════════════════════════════════════════════════
    # NEUE FUNKTIONEN V2.3.0
    # ═══════════════════════════════════════════════════════════════════════
    
    def _is_total_row(self, r: int) -> bool:
        """Prüft ob Zeile die Total-Zeile ist (oberste Zeile bei "Alle")."""
        if not self._is_all_filter():
            return False
        return r == 0
    
    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Behandelt Klicks auf Fix/Wiederkehrend-Spalten."""
        if self._is_header_row(row) or self._is_total_row(row):
            return
        
        cat = self._row_cat_real(row)
        if not cat:
            return
        
        typ = self._row_typ(row)
        
        if col == 1:  # Fix-Spalte
            self._toggle_fix(row, typ, cat)
        elif col == 2:  # Wiederkehrend-Spalte
            self._toggle_recurring(row, typ, cat)
    
    def _toggle_fix(self, row: int, typ: str, cat_name: str) -> None:
        """Schaltet Fix-Status einer Kategorie um."""
        cat_obj = None
        for c in self.cats.list(typ):
            if c.name == cat_name:
                cat_obj = c
                break
        
        if not cat_obj:
            return
        
        new_fix = not bool(cat_obj.is_fix)
        
        self.cats.update_flags(cat_obj.id, is_fix=new_fix, is_recurring=bool(cat_obj.is_recurring), recurring_day=int(cat_obj.recurring_day or 1))
        
        it = self.table.item(row, 1)
        if it:
            it.setText("★" if new_fix else "")
    
    def _toggle_recurring(self, row: int, typ: str, cat_name: str) -> None:
        """Schaltet Wiederkehrend-Status einer Kategorie um."""
        cat_obj = None
        for c in self.cats.list(typ):
            if c.name == cat_name:
                cat_obj = c
                break
        
        if not cat_obj:
            return
        
        new_rec = not bool(cat_obj.is_recurring)
        
        self.cats.update_flags(cat_obj.id, is_fix=bool(cat_obj.is_fix), is_recurring=new_rec, recurring_day=int(cat_obj.recurring_day or 1))
        
        it_rec = self.table.item(row, 2)
        it_day = self.table.item(row, 3)
        
        if it_rec:
            it_rec.setText("∞" if new_rec else "")
        
        if it_day:
            if new_rec:
                it_day.setText(str(cat_obj.recurring_day or 1))
                it_day.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            else:
                it_day.setText("")
                it_day.setFlags(Qt.ItemIsEnabled)
    
    def _insert_total_row(self) -> None:
        """Fügt Total-Zeile als erste Zeile ein."""
        self.table.insertRow(0)
        
        it = QTableWidgetItem(tr("budget.row.budget_balance"))
        font = it.font()
        font.setBold(True)
        font.setPointSize(11)
        it.setFont(font)
        it.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0, 0, it)
        
        for c in [1, 2, 3]:
            empty = QTableWidgetItem("")
            empty.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(0, c, empty)
        
        for c in range(4, 17):
            it = QTableWidgetItem("")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(0, c, it)
    
    def _update_total_row(self) -> None:
        """Aktualisiert Total-Zeile: Einnahmen - Ausgaben - Ersparnisse.
        
        Zeigt Budget-Saldo IMMER an, auch wenn nur ein Typ gefiltert ist.
        Berechnet Saldo aus allen drei Typen (aus DB, nicht aus Tabelle).
        """
        _prev = self._internal_change
        self._internal_change = True
        try:
            if self.table.rowCount() == 0:
                return

            # Immer alle Typen aus DB holen für korrekten Saldo
            year = int(self.year_spin.value())
            totals = {}
            for t in [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]:
                matrix = self.budget.get_matrix(year, t)
                typ_totals = {}
                for month_idx in range(1, 13):
                    typ_totals[month_idx] = sum(matrix.get(cat, {}).get(month_idx, 0.0) for cat in matrix)
                typ_totals[13] = sum(typ_totals.values())  # Jahrestotal
                totals[t] = typ_totals

            einkommen = totals.get(TYP_INCOME, {})
            ausgaben = totals.get(TYP_EXPENSES, {})
            ersparnisse = totals.get(TYP_SAVINGS, {})

            # Monate
            for month_idx in range(1, 13):
                col_idx = month_idx + 3

                ein = einkommen.get(month_idx, 0.0)
                aus = ausgaben.get(month_idx, 0.0)
                ers = ersparnisse.get(month_idx, 0.0)
                saldo = ein - aus - ers

                it = self.table.item(0, col_idx)
                if it:
                    it.setText(fmt_amount(saldo))

                    _c = ui_colors(self)
                    if saldo < -0.01:
                        it.setForeground(QBrush(QColor(_c.negative)))
                    elif saldo > 0.01:
                        it.setForeground(QBrush(QColor(_c.ok)))
                    else:
                        it.setForeground(QBrush(QColor(_c.neutral)))

                    it.setToolTip(
                        f"{tr('kpi.income')}:   {fmt_amount(ein)}\n"
                        f"{tr('kpi.expenses')}:    {fmt_amount(aus)}\n"
                        f"{tr('typ.Ersparnisse')}:  {fmt_amount(ers)}\n"
                        f"─────────────────────\n"
                        f"{tr('lbl.saldo')}:       {fmt_amount(saldo)}"
                    )

            # Jahr
            jahr_ein = einkommen.get(13, 0.0)
            jahr_aus = ausgaben.get(13, 0.0)
            jahr_ers = ersparnisse.get(13, 0.0)
            jahr_saldo = jahr_ein - jahr_aus - jahr_ers

            it_total = self.table.item(0, 16)
            if it_total:
                it_total.setText(fmt_amount(jahr_saldo))

                if jahr_saldo < -0.01:
                    it_total.setForeground(QBrush(QColor(_c.negative)))
                elif jahr_saldo > 0.01:
                    it_total.setForeground(QBrush(QColor(_c.ok)))
                else:
                    it_total.setForeground(QBrush(QColor(_c.neutral)))

                it_total.setToolTip(
                    f"{tr('lbl.annual_income')}:   {fmt_amount(jahr_ein)}\n"
                    f"{tr('lbl.annual_expenses')}:    {fmt_amount(jahr_aus)}\n"
                    f"{tr('lbl.annual_savings')}:  {fmt_amount(jahr_ers)}\n"
                    f"─────────────────────────────\n"
                    f"{tr('lbl.annual_balance')}:       {fmt_amount(jahr_saldo)}"
                )
        finally:
            self._internal_change = _prev
    

    def seed_from_categories(self):
        year = int(self.year_spin.value())
        typ = self._current_typ_db()
        if typ == "Alle":
            types = [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]
        else:
            types = [typ]

        for t in types:
            names = self.cats.list_names(t)
            self.budget.seed_year_from_categories(year, t, names, amount=0.0)

        QMessageBox.information(self, tr("msg.success"), trf("budget.msg.seed_done", typ=display_typ(typ), year=year))
        self.load()

    def load(self):
        year = int(self.year_spin.value())
        typ = self._current_typ_db()

        if typ == "Alle":
            types = [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]
        else:
            types = [typ]

        self._buffer_cache.clear()

        _prev_ic = self._internal_change
        self._internal_change = True
        try:
            self.table.setRowCount(0)

            # Budget-Saldo IMMER anzeigen (auch bei einzelnem Typ)
            self._insert_total_row()
            
            for t in types:
                matrix = self.budget.get_matrix(year, t)
                flat, totals_by_name, buffer_by_name, direct_children_by_name = self._build_tree_flat(t, matrix)

                # Buffer cache (für Footer + Parent-Puffer)
                for name, own in buffer_by_name.items():
                    self._buffer_cache[(t, name)] = dict(own)

                # Typ-Header, wenn "Alle"
                if typ == "Alle" and flat:
                    r = self.table.rowCount()
                    self.table.insertRow(r)
                    header_item = QTableWidgetItem(f"═══ {display_typ(t)} ═══")
                    header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
                    font = header_item.font()
                    font.setBold(True)
                    header_item.setFont(font)
                    try:
                        col = self._typ_color(t)
                        header_item.setForeground(QBrush(col))

                        # Sichtbarer Farb-Header: komplette Zeile dezent einfärben
                        from PySide6.QtGui import QColor
                        bg = QColor(col)
                        bg.setAlpha(35)
                        header_item.setBackground(QBrush(bg))
                        # Restliche Zellen werden erst nach dem Insert gesetzt → später unten nachziehen
                    except Exception as e:
                        logger.debug("header_item color failed: %s", e)
                    header_item.setData(ROLE_TYP, t)
                    self.table.setItem(r, 0, header_item)
                    # Leere Zellen für alle restlichen Spalten (1-16)
                    for c in range(1, 17):
                        empty = QTableWidgetItem("")
                        empty.setFlags(empty.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(r, c, empty)

                    # Background nachziehen (falls Farbe gesetzt wurde)
                    try:
                        col = self._typ_color(t)
                        from PySide6.QtGui import QColor
                        bg = QColor(col)
                        bg.setAlpha(35)
                        for cc in range(1, 17):
                            itx = self.table.item(r, cc)
                            if itx:
                                itx.setBackground(QBrush(bg))
                    except Exception:
                        pass

                for row in flat:
                    name = row["name"]
                    depth = int(row["depth"])
                    has_children = bool(row["has_children"])
                    path = str(row["path"])

                    r = self.table.rowCount()
                    self.table.insertRow(r)

                    collapsed = False
                    if getattr(self, "_tree_view_mode", "tree") == "path":
                        display_name = path
                    else:
                        # Im Baum-Modus: nur den Kategorienamen anzeigen – Einrückung macht die Struktur sichtbar.
                        display_name = tr_category_name(name)
                    
                    is_favorite = self.favorites.is_favorite(t, name)
                    
                    label = self._format_cat_label(display_name, depth, has_children, collapsed)
                    cat_item = QTableWidgetItem(label)
                    cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
                    cat_item.setData(ROLE_TYP, t)
                    cat_item.setData(ROLE_CAT_REAL, name)
                    cat_item.setData(ROLE_DEPTH, depth)
                    cat_item.setData(ROLE_HAS_CHILDREN, has_children)
                    cat_item.setData(ROLE_PATH, path)
                    cat_item.setData(ROLE_COLLAPSED, False)
                    cat_item.setToolTip(path)
                    if is_favorite:
                        cat_item.setIcon(get_icon("⭐"))
                    self.table.setItem(r, 0, cat_item)

                    # Spalte 1: Fix (Fix)
                    is_fix = row.get("is_fix", False)
                    it_fix = QTableWidgetItem("★" if is_fix else "")
                    it_fix.setTextAlignment(Qt.AlignCenter)
                    it_fix.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    it_fix.setData(ROLE_TYP, t)
                    it_fix.setData(ROLE_CAT_REAL, name)
                    it_fix.setToolTip(tr("budget.tooltip.toggle"))
                    self.table.setItem(r, 1, it_fix)
                    
                    # Spalte 2: Wiederkehrend (∞)
                    is_rec = row.get("is_recurring", False)
                    it_rec = QTableWidgetItem("∞" if is_rec else "")
                    it_rec.setTextAlignment(Qt.AlignCenter)
                    it_rec.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    it_rec.setData(ROLE_TYP, t)
                    it_rec.setData(ROLE_CAT_REAL, name)
                    it_rec.setToolTip(tr("budget.tooltip.toggle"))
                    self.table.setItem(r, 2, it_rec)
                    
                    # Spalte 3: Tag
                    rec_day = row.get("recurring_day", 1)
                    it_day = QTableWidgetItem(str(rec_day) if is_rec else "")
                    it_day.setTextAlignment(Qt.AlignCenter)
                    if is_rec:
                        it_day.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    else:
                        it_day.setFlags(Qt.ItemIsEnabled)
                    it_day.setData(ROLE_TYP, t)
                    it_day.setData(ROLE_CAT_REAL, name)
                    self.table.setItem(r, 3, it_day)

                    # Typ-Farbe auf Label/Badges anwenden (Spalten 0-3)
                    try:
                        col = self._typ_color(t)
                        brush = QBrush(col)
                        for cc in range(0, 4):
                            itx = self.table.item(r, cc)
                            if itx:
                                itx.setForeground(brush)
                                from PySide6.QtGui import QColor
                                bg = QColor(col)
                                bg.setAlpha(18)
                                itx.setBackground(QBrush(bg))
                    except Exception as e:
                        logger.debug("col = self._typ_color(t): %s", e)

                    _SEP = "─" * 26
                    row_total = 0.0
                    row_buf_total = 0.0
                    row_child_total = 0.0
                    for m in range(1, 13):  # m = logischer Monat (1-12)
                        col_idx = m + 3  # Spalte 4-15 (wegen Fix/Wiederkehrend/Tag davor)

                        total_val = float(totals_by_name.get(name, {}).get(m, 0.0))
                        own_val   = float(buffer_by_name.get(name, {}).get(m, 0.0))
                        child_val = float(total_val - own_val)

                        _cell_text = fmt_amount(total_val)
                        it = QTableWidgetItem(_cell_text)
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        it.setData(ROLE_TYP, t)
                        if has_children:
                            ch_names = direct_children_by_name.get(name, [])
                            lines = [f"{tr('budget.tooltip.puffer')}:  {max(0.0, own_val):.2f}", _SEP]
                            for ch in ch_names:
                                ch_v = float(totals_by_name.get(ch, {}).get(m, 0.0))
                                lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_v)}")
                            ch_sum = sum(
                                float(totals_by_name.get(ch, {}).get(m, 0.0))
                                for ch in ch_names
                            )
                            lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_sum)}"]
                            it.setToolTip("\n".join(lines))
                        else:
                            it.setToolTip(path)

                        self.table.setItem(r, col_idx, it)
                        row_total      += total_val
                        row_buf_total  += own_val
                        row_child_total += child_val

                    if has_children:
                        ch_names = direct_children_by_name.get(name, [])
                        _puffer_year = max(0.0, row_buf_total)
                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {_puffer_year:.2f}", _SEP]
                        for ch in ch_names:
                            ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                            tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
                        ch_year_sum = sum(
                            sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                            for ch in ch_names
                        )
                        tot_lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_year_sum)}"]
                        tot_tip = "\n".join(tot_lines)
                        tot_text = fmt_amount(row_total)
                    else:
                        tot_tip = path
                        tot_text = fmt_amount(row_total)

                    tot = QTableWidgetItem(tot_text)
                    tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    tot.setToolTip(tot_tip)

                    # Total-Spalte: Parent mit Children -> read-only
                    if has_children:
                        tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(r, 16, tot)

            # Budget-Saldo immer aktualisieren
            self._update_total_row()
                
            self._reapply_tree_visibility()
            self._apply_table_styles()
            self.table.resizeColumnsToContents()
            self._update_overview_bar()
        finally:
            self._internal_change = _prev_ic

    # Einheitliches API: MainWindow kann beim Tab-Wechsel `refresh()` nutzen.
    def refresh(self) -> None:
        self.load()

    # -----------------------------
    # Parent recalculation helpers
    # -----------------------------
    def _build_parent_tooltip(self, parent_row: int, month_col: int) -> str:
        """Tooltip für eine Parent-Monatszelle.

        Format (i18n):
          [budget.tooltip.puffer]:  <Gesamtwert der Zelle>
          ──────────────────────────
            Kind-A:  X.XX
            Kind-B:  Y.YY
          ──────────────────────────
          [budget.tooltip.children_sum]:  Z.ZZ
        """
        parent_depth = self._row_depth(parent_row)
        logical_m    = month_col - 3

        # Puffer aus Cache lesen (nicht aus Zelltext — Zelle zeigt nur blanken Puffer)
        typ_p = self._row_typ(parent_row)
        cat_p = self._row_cat_real(parent_row)
        puffer_val = max(0.0, float(self._buffer_cache.get((typ_p, cat_p), {}).get(logical_m, 0.0)))

        children: list[tuple[str, float]] = []
        data_rows = self._row_count_data()
        i = parent_row + 1
        while i < data_rows:
            if self._is_header_row(i):
                break
            d = self._row_depth(i)
            if d <= parent_depth:
                break
            if d == parent_depth + 1:
                ch_cat = self._row_cat_real(i)
                it = self.table.item(i, month_col)
                ch_val = _parse_cell_amount(it.text() if it else "")
                if ch_cat:
                    children.append((tr_category_name(ch_cat), ch_val))
            i += 1

        children_sum = sum(v for _, v in children)
        total_val = puffer_val + children_sum
        sep = "─" * 28
        lines = [f"{tr('budget.tooltip.puffer')}:  {puffer_val:.2f}", sep]
        for ch_name, ch_val in children:
            lines.append(f"  {ch_name}:  {fmt_amount(ch_val)}")
        lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(children_sum)}"]
        return "\n".join(lines)

    def _sum_immediate_children_month(self, parent_row: int, month_col: int) -> float:
        """Summe der unmittelbaren Children (depth+1) für einen Monat.

        Wichtig: Wir summieren NUR depth+1-Zeilen, weil diese bereits ihre Subtrees enthalten.
        """
        parent_depth = self._row_depth(parent_row)
        if parent_depth < 0:
            return 0.0

        data_rows = self._row_count_data()
        total = 0.0
        i = parent_row + 1
        while i < data_rows:
            if self._is_header_row(i):
                break
            d = self._row_depth(i)
            if d <= parent_depth:
                break
            if d == parent_depth + 1:
                it = self.table.item(i, month_col)
                total += _parse_cell_amount(it.text() if it else "")
            i += 1
        return total

    def _update_parent_chain(self, start_row: int, month_col: int):
        """Rechnet für diesen Monat alle Parent-Zeilen nach oben neu.
        
        Args:
            start_row: Ausgangszeile
            month_col: Spaltenindex (4-15 für Jan-Dez)
        """
        data_rows = self._row_count_data()
        if start_row >= data_rows:
            return

        cur_row = start_row
        cur_depth = self._row_depth(cur_row)
        if cur_depth <= 0:
            return
        
        # Logischer Monat für Buffer-Cache (1-12)
        logical_month = month_col - 3

        # Suche Parents über die Depth-Hierarchie
        while cur_depth > 0:
            # Parent ist die nächste Zeile oberhalb mit depth = cur_depth - 1
            p = cur_row - 1
            parent_row = None
            while p >= 0:
                if self._is_header_row(p):
                    break
                d = self._row_depth(p)
                if d == cur_depth - 1:
                    parent_row = p
                    break
                p -= 1

            if parent_row is None:
                return

            typ = self._row_typ(parent_row)
            cat = self._row_cat_real(parent_row)
            if not cat:
                return

            buf = float(self._buffer_cache.get((typ, cat), {}).get(logical_month, 0.0))
            children_sum = self._sum_immediate_children_month(parent_row, month_col)
            new_total = buf + children_sum

            # Update cell — zeigt puffer + kinder (stabil bei Reload)
            it = self.table.item(parent_row, month_col)
            if it is None:
                it = QTableWidgetItem()
                self.table.setItem(parent_row, month_col, it)
            _prev = self._internal_change
            self._internal_change = True
            try:
                it.setText(fmt_amount(new_total))
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it.setToolTip(self._build_parent_tooltip(parent_row, month_col))
            finally:
                self._internal_change = _prev

            self._recalc_row_total(parent_row)

            # Weiter nach oben
            cur_row = parent_row
            cur_depth -= 1

    # -----------------------------
    # Footer / totals
    # -----------------------------
    def _recalc_footer(self):
        _prev = self._internal_change
        self._internal_change = True
        try:
            self._recalc_footer_inner()
        finally:
            self._internal_change = _prev

    def _recalc_footer_inner(self):
        # remove existing footer row
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text() == "TOTAL":
                self.table.removeRow(r)
                break

        if self.table.rowCount() == 0:
            return

        footer = self.table.rowCount()
        self.table.insertRow(footer)

        title = QTableWidgetItem("TOTAL")
        title.setFlags(title.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(footer, 0, title)

        data_rows = footer

        grand = 0.0
        for m in range(1, 13):
            col_sum = 0.0
            for r in range(data_rows):
                if self._is_header_row(r):
                    continue
                cat = self._row_cat_real(r)
                if not cat:
                    continue
                typ = self._row_typ(r)
                has_children = self._row_has_children(r)

                if has_children:
                    # Parent: nur Puffer zählen (keine Doppelzählung)
                    col_sum += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
                else:
                    # Spalten: 0=Bezeichnung, 1=Fix, 2=∞, 3=Tag, 4-15=Monate, 16=Total
                    # Monat m (1-12) entspricht Spalte m+3 (4-15)
                    it = self.table.item(r, m + 3)
                    col_sum += parse_amount(it.text() if it else "")

            grand += col_sum
            cell = QTableWidgetItem(fmt_amount(col_sum))
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Footer-Zellen auch auf Spalte m+3 setzen
            self.table.setItem(footer, m + 3, cell)

        gcell = QTableWidgetItem(fmt_amount(grand))
        gcell.setFlags(gcell.flags() & ~Qt.ItemIsEditable)
        gcell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(footer, 16, gcell)  # Total ist Spalte 16

        # Styling + Übersicht aktualisieren (damit TOTAL/Parent/Headers sauber bleiben)
        self._apply_table_styles()
        self._update_overview_bar()

    def _persist_single_cell(self, r: int, month_col: int):
        """Speichert eine einzelne Monatszelle.
        
        Args:
            r: Zeilenindex
            month_col: Spaltenindex (4-15 für Jan-Dez)
        """
        year = int(self.year_spin.value())
        typ = self._row_typ(r)
        cat = self._row_cat_real(r)
        if not cat:
            return

        it = self.table.item(r, month_col)
        amt = parse_amount(it.text() if it else "")

        # Bei Parent mit Children: amt ist Display (buffer+children) -> wir speichern NUR buffer
        if self._row_has_children(r):
            # buffer bleibt im cache/DB – hier NICHT überschreiben
            return

        if typ == TYP_EXPENSES and amt < 0:
            amt = abs(amt)
        
        # Spalte 4-15 -> Logischer Monat 1-12
        logical_month = month_col - 3
        self.budget.set_amount(year, logical_month, typ, cat, amt)
        self.budget_data_changed.emit()

    def _get_db_value(self, typ: str, cat: str, month: int) -> float:
        year = int(self.year_spin.value())
        mat = self.budget.get_matrix(year, typ)
        return float(mat.get(cat, {}).get(month, 0.0))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._internal_change:
            return

        r = item.row()
        c = item.column()

        # Nicht-editierbare Zeilen/Spalten
        if self._is_total_row(r) or self._is_footer_row(r) or self._is_header_row(r):
            return
        if c <= 2:  # Bezeichnung, Fix-Status, Wiederkehrend
            return

        # Spalte 3: Tag (recurring_day)
        if c == 3:
            self._handle_recurring_day_edit(item, r)
            return

        typ = self._row_typ(r)
        cat = self._row_cat_real(r)
        if not cat:
            return

        has_children = self._row_has_children(r)

        # Parent + Children: Total-Spalte ist read-only
        if has_children and c == 16:
            return
        # Total-Spalte → auf Monate verteilen (nur Leaf)
        if c == 16 and not has_children:
            self._handle_total_column_edit(item, r, typ, cat)
            return

        # Monatsspalten 4–15
        if 4 <= c <= 15:
            month = c - 3
            if has_children:
                self._handle_parent_month_edit(item, r, c, month, typ, cat)
                return
            if self.chk_ask_due.isChecked():
                self._handle_leaf_ask_due(item, r, c, month, typ, cat)
                return

        # Normal direct edit: normalize + totals + optional autosave
        self._handle_normal_edit(item, r, c, typ)

    # ── _on_item_changed Hilfsmethoden ───────────────────────────

    def _handle_recurring_day_edit(self, item: QTableWidgetItem, r: int) -> None:
        """Spalte 3: recurring_day bearbeiten."""
        typ = self._row_typ(r)
        cat = self._row_cat_real(r)
        if not cat:
            return

        cat_obj = None
        for c_obj in self.cats.list(typ):
            if c_obj.name == cat:
                cat_obj = c_obj
                break

        if not cat_obj or not cat_obj.is_recurring:
            return

        try:
            new_day = int(item.text())
            if new_day < 1 or new_day > 31:
                raise ValueError("Tag muss 1-31 sein")
        except Exception:
            _prev = self._internal_change
            self._internal_change = True
            item.setText(str(cat_obj.recurring_day or 1))
            self._internal_change = _prev
            QMessageBox.warning(self, tr("msg.info"), tr("msg.invalid_day"))
            return

        self.cats.update_flags(cat_obj.id, is_fix=bool(cat_obj.is_fix), is_recurring=True, recurring_day=new_day)

    def _handle_total_column_edit(self, item: QTableWidgetItem, r: int, typ: str, cat: str) -> None:
        """Spalte 16: Jahres-Total editiert → gleichmäßig auf 12 Monate verteilen."""
        try:
            total = parse_amount(item.text())
        except Exception:
            total = 0.0
        if typ == TYP_EXPENSES and total < 0:
            total = abs(total)
            QMessageBox.information(self, tr("msg.info"), tr("msg.negative_not_allowed"))

        base = round(total / 12.0, 2)
        last = round(total - base * 11, 2)

        _prev = self._internal_change
        self._internal_change = True
        try:
            for col_idx in range(4, 15):
                it = self.table.item(r, col_idx)
                if it is None:
                    it = QTableWidgetItem()
                    self.table.setItem(r, col_idx, it)
                it.setText(fmt_amount(base))
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_dez = self.table.item(r, 15)
            if it_dez is None:
                it_dez = QTableWidgetItem()
                self.table.setItem(r, 15, it_dez)
            it_dez.setText(fmt_amount(last))
            it_dez.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setText(fmt_amount(total))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = _prev

        self._recalc_row_total(r)
        for m in range(1, 13):
            self._update_parent_chain(r, m + 3)

        if self._is_all_filter():
            self._update_total_row()

    def _handle_parent_month_edit(self, item: QTableWidgetItem, r: int, c: int, month: int, typ: str, cat: str) -> None:
        """Parent-Zeile: Monatszelle editiert → Eingabe = Puffer (Zusatzbudget).

        Der Nutzer gibt den PUFFER ein (z.B. 50 für Selbstbehalt).
        Anzeige = Puffer + Kinder-Summe (z.B. 50 + 1600 = 1650.00).
        """
        typed_puffer = parse_amount(item.text())
        if typ == TYP_EXPENSES and typed_puffer < 0:
            typed_puffer = abs(typed_puffer)
            QMessageBox.information(self, tr("msg.info"), tr("msg.negative_not_allowed"))

        year = int(self.year_spin.value())

        # Puffer direkt speichern
        self.budget.set_amount(year, month, typ, cat, typed_puffer)
        self._buffer_cache.setdefault((typ, cat), {})[month] = float(typed_puffer)
        self.budget_data_changed.emit()

        children_sum = self._sum_immediate_children_month(r, c)
        display = typed_puffer + children_sum

        _prev = self._internal_change
        self._internal_change = True
        try:
            item.setText(fmt_amount(display))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setToolTip(self._build_parent_tooltip(r, c))
        finally:
            self._internal_change = _prev

        self._recalc_row_total(r)
        self._update_parent_chain(r, c)
        self._recalc_footer()

    def _handle_leaf_ask_due(self, item: QTableWidgetItem, r: int, c: int, month: int, typ: str, cat: str) -> None:
        """Leaf-Zelle mit ask_due-Dialog: zeigt Detaileingabe-Dialog."""
        try:
            typed = parse_amount(item.text())
        except Exception:
            typed = 0.0
        if typ == TYP_EXPENSES and typed < 0:
            typed = abs(typed)

        prev = self._get_db_value(typ, cat, month)
        _prev_flag = self._internal_change
        self._internal_change = True
        try:
            item.setText(fmt_amount(prev))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = _prev_flag

        _, is_rec, _day = self.cats.get_flags(typ, cat)
        default_mode = "Alle" if is_rec else "Monat"
        dlg = BudgetEntryDialog(
            self,
            default_year=int(self.year_spin.value()),
            default_typ=typ,
            categories=(self.cats.list_names_tree(typ) if hasattr(self.cats, "list_names_tree") else self.cats.list_names(typ)),
            preset={"category": cat, "amount": typed, "month": month, "mode": default_mode, "only_if_empty": False},
        )
        if dlg.exec() == QDialog.Accepted:
            self._apply_request(dlg.get_request())

    def _handle_normal_edit(self, item: QTableWidgetItem, r: int, c: int, typ: str) -> None:
        """Standard-Zelledit: Normalisieren, Totals aktualisieren, ggf. Auto-Save."""
        try:
            val = parse_amount(item.text())
        except Exception:
            val = 0.0

        if typ == TYP_EXPENSES and val < 0:
            val = abs(val)
            QMessageBox.information(self, tr("msg.info"), tr("msg.negative_not_allowed"))

        _prev = self._internal_change
        self._internal_change = True
        try:
            item.setText(fmt_amount(val))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = _prev

        self._recalc_row_total(r)
        if 4 <= c <= 15:
            self._update_parent_chain(r, c)
        self._recalc_footer()

        if self.chk_autosave.isChecked() and (4 <= c <= 15):
            self._persist_single_cell(r, c)

    def _recalc_row_total(self, r: int):
        data_rows = self._row_count_data()
        if r >= data_rows:
            return
        if self._is_header_row(r):
            return
        if self._is_total_row(r):
            return  # Total-Zeile wird separat berechnet
        has_children = self._row_has_children(r)

        row_total = 0.0
        for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
            it = self.table.item(r, col_idx)
            row_total += _parse_cell_amount(it.text() if it else "")

        tot = self.table.item(r, 16)  # Spalte 16 (Total)
        if tot is None:
            tot = QTableWidgetItem()
            self.table.setItem(r, 16, tot)

        _prev = self._internal_change
        self._internal_change = True
        try:
            if has_children:
                typ = self._row_typ(r)
                cat = self._row_cat_real(r)
                row_buf_total = 0.0
                row_child_total = 0.0
                if cat:
                    for m in range(1, 13):
                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
                sep = "─" * 26
                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
                data_rows = self._row_count_data()
                parent_depth = self._row_depth(r)
                i = r + 1
                while i < data_rows:
                    if self._is_header_row(i):
                        break
                    d = self._row_depth(i)
                    if d <= parent_depth:
                        break
                    if d == parent_depth + 1:
                        ch_cat = self._row_cat_real(i)
                        if ch_cat:
                            ch_year = 0.0
                            for mm in range(4, 16):
                                it_ch = self.table.item(i, mm)
                                ch_year += parse_amount(it_ch.text() if it_ch else "")
                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
                    i += 1
                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
                tot.setText(fmt_amount(row_total))
                tot.setToolTip("\n".join(tot_lines))
                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
            else:
                tot.setText(fmt_amount(row_total))
            tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = _prev

    def save(self):
        year = int(self.year_spin.value())
        data_rows = self._row_count_data()

        for r in range(data_rows):
            if self._is_header_row(r):
                continue
            if self._is_total_row(r):
                continue  # Total-Zeile nicht speichern
            cat = self._row_cat_real(r)
            if not cat:
                continue
            typ = self._row_typ(r)
            has_children = self._row_has_children(r)

            # Parent mit Children: Monatszellen zeigen Total, speichern wäre falsch.
            # Buffer wurde beim Edit sofort gespeichert.
            if has_children:
                continue

            for m in range(1, 13):  # Logische Monate 1-12
                col_idx = m + 3  # Spalten 4-15
                it = self.table.item(r, col_idx)
                amt = parse_amount(it.text() if it else "")
                if typ == TYP_EXPENSES and amt < 0:
                    amt = abs(amt)
                self.budget.set_amount(year, m, typ, cat, amt)
            self._recalc_row_total(r)

        # Total-Zeile aktualisieren (wenn vorhanden)
        if self._is_all_filter():
            self._update_total_row()
        
        # Automatische Budgetwarnungen erstellen (90% Schwelle)
        self._create_auto_warnings(year)
        
        # Keine störende MessageBox mehr - Speichern erfolgt still
        self.budget_data_changed.emit()

    def _apply_request(self, req: BudgetEntryRequest):
        # Kategorie wird jetzt automatisch im Dialog erstellt
        # Falls sie trotzdem fehlt (z.B. alter Dialog), erstellen wir sie hier
        if req.category not in self.cats.list_names(req.typ):
            # Automatisch als Hauptkategorie erstellen
            try:
                self.cats.create(
                    typ=req.typ,
                    name=req.category,
                    is_fix=False,
                    is_recurring=False,
                    parent_id=None
                )
            except Exception as e:
                QMessageBox.warning(
                    self, tr("budget.title.category_error"), 
                    trf("budget.msg.create_category_failed", category=req.category, error=e)
                )
                return

        self.budget.seed_year_from_categories(req.year, req.typ, [req.category], amount=0.0)

        if req.mode == "Alle":
            months = list(range(1, 13))
        elif req.mode == "Bereich":
            a, b = sorted([req.from_month, req.to_month])
            months = list(range(a, b + 1))
        else:
            months = [req.month]

        for m in months:
            amt = abs(req.amount) if (req.typ == TYP_EXPENSES and req.amount < 0) else req.amount

            if req.only_if_empty:
                mat = self.budget.get_matrix(req.year, req.typ)
                current = mat.get(req.category, {}).get(m, 0.0)
                if abs(float(current)) > 1e-9:
                    continue

            self.budget.set_amount(req.year, m, req.typ, req.category, amt)

        self.year_spin.setValue(req.year)
        _key_to_set = "" if req.typ == "Alle" else req.typ
        _idx = self.typ_cb.findData(_key_to_set)
        if _idx >= 0:
            self.typ_cb.setCurrentIndex(_idx)
        self.load()
        self._focus_category_month(req.category, months[0])

    def _focus_category_month(self, category: str, month: int, typ: str | None = None) -> bool:
        data_rows = self._row_count_data()
        for r in range(data_rows):
            if self._is_header_row(r):
                continue
            it = self.table.item(r, 0)
            if not it or it.data(ROLE_CAT_REAL) != category:
                continue
            if typ and self._row_typ(r) != typ:
                continue
            col = max(4, min(15, month + 3))
            self.table.setCurrentCell(r, col)
            return True
        return False

    def focus_budget_entry(self, *, typ: str, category: str, year: int, month: int, open_dialog: bool = False) -> bool:
        """Fokussiert einen Budgeteintrag für externe Navigation (z.B. Übersicht-Tab)."""
        self.year_spin.setValue(int(year))
        idx = self.typ_cb.findData(typ or "")
        if idx < 0:
            idx = self.typ_cb.findData("")
        if idx >= 0:
            self.typ_cb.setCurrentIndex(idx)
        self.load()
        found = self._focus_category_month(category, month, typ=typ)
        if found and open_dialog:
            self.open_edit_dialog()
        return found

    def open_entry_dialog(self):
        year = int(self.year_spin.value())

        # wenn "Alle": versuche typ vom aktuell selektierten Row zu nehmen
        r = self.table.currentRow()
        if r >= 0 and r < self._row_count_data() and not self._is_header_row(r):
            typ = self._row_typ(r)
            cat = self._row_cat_real(r)
        else:
            _d = self.typ_cb.currentData()
            typ = TYP_EXPENSES if not _d else _d
            cat = None

        preset = None
        if cat:
            _, is_rec, _day = self.cats.get_flags(typ, cat)
            preset = {"category": cat, "mode": ("Alle" if is_rec else "Monat")}

        # Verwende den erweiterten Dialog mit integrierter Kategorie-Verwaltung
        dlg = BudgetEntryDialogExtended(
            self, 
            conn=self.conn,
            default_year=year, 
            default_typ=typ, 
            preset=preset
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self._apply_request(dlg.get_request())

    def open_edit_dialog(self):
        r = self.table.currentRow()
        c = self.table.currentColumn()
        if r < 0 or c < 4 or c > 15:
            QMessageBox.information(self, tr("msg.info"), tr("budget.msg.select_month_cell"))
            return
        if self._is_header_row(r) or self._is_footer_row(r):
            return

        cat = self._row_cat_real(r)
        typ = self._row_typ(r)
        if not cat:
            return

        # Bei Parent mit Children: Bearbeiten öffnet Dialog NICHT (sonst verwirrend)
        if self._row_has_children(r):
            QMessageBox.information(
                self,
                tr("msg.info"),
                tr("budget.msg.parent_has_children") + "\n" + tr("budget.msg.edit_buffer_help_short"),
            )
            return

        current_txt = self.table.item(r, c).text() if self.table.item(r, c) else ""
        current_val = parse_amount(current_txt) if current_txt else 0.0

        year = int(self.year_spin.value())

        _, is_rec, _day = self.cats.get_flags(typ, cat)
        default_mode = "Alle" if is_rec else "Monat"

        # Verwende den erweiterten Dialog mit integrierter Kategorie-Verwaltung
        dlg = BudgetEntryDialogExtended(
            self,
            conn=self.conn,
            default_year=year,
            default_typ=typ,
            preset={"category": cat, "amount": current_val, "month": c - 3, "mode": default_mode, "only_if_empty": False},
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self._apply_request(dlg.get_request())

    def _selected_category(self) -> tuple[str, str] | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        if self._is_footer_row(r) or self._is_header_row(r):
            return None
        cat = self._row_cat_real(r)
        if not cat:
            return None
        typ = self._row_typ(r)
        return (typ, cat)

    def remove_budget_row(self):
        sel = self._selected_category()
        if not sel:
            QMessageBox.information(self, tr("msg.info"), tr("budget.msg.select_category_row"))
            return
        typ, cat = sel
        year = int(self.year_spin.value())

        if QMessageBox.question(
            self,
            tr("msg.remove_budget_row"),
            trf("budget.msg.remove_row_confirm", category=cat, typ=display_typ(typ), year=year),
        ) != QMessageBox.Yes:
            return

        self.budget.delete_category_for_year(year, typ, cat)
        self.load()

    def delete_category_global(self):
        sel = self._selected_category()
        if not sel:
            QMessageBox.information(self, tr("msg.info"), tr("budget.msg.select_category_row"))
            return
        typ, cat = sel

        msg = tr("budget.msg.delete_global_warn_1") + trf("budget.msg.delete_global_warn_2", cat=cat, typ=display_typ(typ))

        if QMessageBox.question(self, tr("budget.title.delete_category"), msg) != QMessageBox.Yes:
            return

        self.budget.delete_category_all_years(typ, cat)
        self.cats.delete(typ, cat)
        self.load()

    def copy_year_dialog(self):
        default_src = int(self.year_spin.value())
        dlg = CopyYearDialog(self, default_src=default_src, known_years=self.budget.years())
        if dlg.exec() != QDialog.Accepted:
            return
        req = dlg.get_request()

        if req.src_year == req.dst_year:
            QMessageBox.warning(self, tr("msg.warning"), tr("budget.msg.copy_year_diff"))
            return

        typ = None if req.scope_typ == "Alle" else req.scope_typ
        self.budget.copy_year(req.src_year, req.dst_year, carry_amounts=req.carry_amounts, typ=typ)

        if typ is None:
            for t in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
                self.budget.seed_year_from_categories(req.dst_year, t, self.cats.list_names(t), amount=0.0)
        else:
            self.budget.seed_year_from_categories(req.dst_year, typ, self.cats.list_names(typ), amount=0.0)

        QMessageBox.information(self, tr("msg.success"), trf("budget.msg.copy_year_done", src=req.src_year, dst=req.dst_year))
        self.year_spin.setValue(req.dst_year)
        self.load()

    # =========================================================================
    # RECHTSKLICK-KONTEXTMENÜ
    # =========================================================================
    def _show_context_menu(self, pos) -> None:
        """Zeigt Kontextmenü für Rechtsklick auf Tabelle."""
        item = self.table.itemAt(pos)
        if not item:
            return
        
        row = item.row()
        col = item.column()
        
        # Nicht auf Header/Footer
        if self._is_header_row(row) or self._is_footer_row(row):
            return
        
        cat = self._row_cat_real(row)
        typ = self._row_typ(row)
        if not cat:
            return
        
        # Kategorie-Infos laden
        cat_obj = None
        for c in self.cats.list(typ):
            if c.name == cat:
                cat_obj = c
                break
        
        menu = QMenu(self)
        
        # === Kategorie-Aktionen ===
        menu.addSection(trf("budget.ctx.section_category", category=cat))
        
        act_props = menu.addAction(tr("budget.ctx.properties"))
        act_rename = menu.addAction(tr("budget.ctx.rename"))
        
        menu.addSeparator()
        
        # Flags-Toggle (direkt umschaltbar)
        if cat_obj:
            fix_text = tr("budget.ctx.fix_disable") if cat_obj.is_fix else tr("budget.ctx.fix_enable")
            act_toggle_fix = menu.addAction(fix_text)
            
            rec_text = tr("budget.ctx.rec_disable") if cat_obj.is_recurring else tr("budget.ctx.rec_enable")
            act_toggle_rec = menu.addAction(rec_text)
            
            act_set_day = menu.addAction(trf("budget.ctx.set_due_day", day=cat_obj.recurring_day))
        else:
            act_toggle_fix = None
            act_toggle_rec = None
            act_set_day = None
        
        menu.addSeparator()
        
        act_new = menu.addAction(tr("budget.ctx.new_category"))
        act_new_sub = menu.addAction(tr("budget.ctx.new_subcategory"))
        
        menu.addSeparator()
        
        act_delete_budget = menu.addAction(tr("budget.ctx.delete_row_this_year"))
        act_delete_cat = menu.addAction(tr("budget.ctx.delete_category"))
        
        menu.addSeparator()
        
        # === Favoriten ===
        menu.addSection(tr("budget.ctx.section_favorites"))
        
        is_favorite = self.favorites.is_favorite(typ, cat)
        if is_favorite:
            act_unfavorite = menu.addAction(tr("budget.ctx.unfavorite"))
        else:
            act_favorite = menu.addAction(tr("budget.ctx.favorite"))
        
        menu.addSeparator()
        
        # === Budget-Aktionen ===
        menu.addSection(tr("budget.ctx.section_budget"))
        
        act_edit = menu.addAction(tr("budget.ctx.edit_budget"))
        act_copy_row = menu.addAction(tr("budget.ctx.copy_row_all_months"))
        
        # Aktion ausführen
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action is None:
            return
        
        # Favoriten-Aktionen
        is_favorite = self.favorites.is_favorite(typ, cat)
        if is_favorite and action == act_unfavorite:
            self._remove_favorite(typ, cat)
            return
        elif (not is_favorite) and action == act_favorite:
            self._add_favorite(typ, cat)
            return
        
        if action == act_props:
            self._edit_category_properties(cat, typ)
        elif action == act_rename:
            self._rename_category_inline(cat, typ)
        elif action == act_toggle_fix and cat_obj:
            self._toggle_category_fix(cat_obj)
        elif action == act_toggle_rec and cat_obj:
            self._toggle_category_recurring(cat_obj)
        elif action == act_set_day and cat_obj:
            self._set_category_day(cat_obj)
        elif action == act_new:
            self._create_new_category(typ)
        elif action == act_new_sub:
            self._create_subcategory(cat, typ)
        elif action == act_delete_budget:
            self._delete_budget_row_for_category(cat, typ)
        elif action == act_delete_cat:
            self._delete_category_with_confirm(cat, typ)
        elif action == act_edit:
            self.open_edit_dialog()
        elif action == act_copy_row:
            self._copy_row_to_all_months(row)
    
    def _edit_category_properties(self, cat_name: str, typ: str) -> None:
        """Öffnet den Eigenschaften-Dialog für eine Kategorie."""
        dlg = CategoryPropertiesDialog(
            self,
            conn=self.conn,
            category_name=cat_name,
            typ=typ
        )
        dlg.category_updated.connect(self.load)
        dlg.exec()
    
    def _rename_category_inline(self, cat_name: str, typ: str) -> None:
        """Benennt eine Kategorie um."""
        new_name, ok = QInputDialog.getText(
            self, tr("budget.title.rename_category"),
            f"Neuer Name für '{cat_name}':",
            text=cat_name
        )
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == cat_name:
            return
        
        # Prüfen ob Name bereits existiert
        if new_name in self.cats.list_names(typ):
            QMessageBox.warning(
                self, tr("msg.error"),
                f"Eine Kategorie mit dem Namen '{new_name}' existiert bereits."
            )
            return
        
        # Kategorie-ID finden
        cat_id = None
        for c in self.cats.list(typ):
            if c.name == cat_name:
                cat_id = c.id
                break
        
        if cat_id is None:
            return
        
        try:
            self.cats.rename_and_cascade(
                cat_id, typ=typ,
                old_name=cat_name, new_name=new_name
            )
            self.load()
            QMessageBox.information(
                self, tr("msg.success"),
                trf("budget.msg.renamed", old=cat_name, new=new_name)
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("budget.msg.rename_failed", error=e))
    
    def _toggle_category_fix(self, cat: Category) -> None:
        """Schaltet Fixkosten-Flag um."""
        try:
            new_val = not cat.is_fix
            self.cats.update_flags(cat.id, is_fix=new_val)
            status = "aktiviert" if new_val else "deaktiviert"
            QMessageBox.information(self, tr("msg.success"), trf("budget.msg.fix_toggled", category=cat.name, status=status))
            self.load()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("budget.msg.change_failed", error=e))
    
    def _toggle_category_recurring(self, cat: Category) -> None:
        """Schaltet Wiederkehrend-Flag um."""
        try:
            new_val = not cat.is_recurring
            self.cats.update_flags(cat.id, is_recurring=new_val)
            status = "aktiviert" if new_val else "deaktiviert"
            QMessageBox.information(self, tr("msg.success"), trf("budget.msg.rec_toggled", category=cat.name, status=status))
            self.load()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("budget.msg.change_failed", error=e))
    
    def _set_category_day(self, cat: Category) -> None:
        """Setzt den Fälligkeitstag."""
        day, ok = QInputDialog.getInt(
            self, tr("budget.title.set_due_day"),
            trf("budget.msg.set_due_day_prompt", category=cat.name),
            cat.recurring_day, 1, 31
        )
        if not ok:
            return
        
        try:
            self.cats.update_flags(cat.id, is_recurring=True, recurring_day=day)
            QMessageBox.information(
                self, tr("msg.success"),
                trf("budget.msg.set_due_day_done", category=cat.name, day=day)
            )
            self.load()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("budget.msg.change_failed", error=e))
    
    def _create_new_category(self, typ: str) -> None:
        """Erstellt eine neue Kategorie."""
        dlg = QuickCategoryDialog(
            self,
            conn=self.conn,
            default_typ=typ
        )
        if dlg.exec() == QDialog.Accepted:
            self.load()
    
    def _create_subcategory(self, parent_name: str, typ: str) -> None:
        """Erstellt eine Unterkategorie."""
        # Parent-ID finden
        parent_id = None
        for c in self.cats.list(typ):
            if c.name == parent_name:
                parent_id = c.id
                break
        
        name, ok = QInputDialog.getText(
            self, tr("budget.title.new_subcategory"),
            f"Name der neuen Unterkategorie unter '{parent_name}':"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        try:
            self.cats.create(
                typ=typ,
                name=name,
                is_fix=False,
                is_recurring=False,
                parent_id=parent_id
            )
            self.load()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("budget.msg.create_failed", error=e))
    
    def _delete_budget_row_for_category(self, cat: str, typ: str) -> None:
        """Löscht nur die Budget-Zeile für dieses Jahr."""
        year = int(self.year_spin.value())
        
        if QMessageBox.question(
            self,
            tr("msg.remove_budget_row"),
            trf("budget.msg.remove_row_confirm_short", category=cat, year=year)
        ) != QMessageBox.Yes:
            return
        
        self.budget.delete_category_for_year(year, typ, cat)
        self.load()
    
    def _delete_category_with_confirm(self, cat: str, typ: str) -> None:
        """Löscht Kategorie mit Bestätigung."""
        # Unterkategorien prüfen
        all_cats = self.cats.list(typ)
        cat_obj = None
        children = []
        
        for c in all_cats:
            if c.name == cat:
                cat_obj = c
            elif c.parent_id:
                parent = next((p for p in all_cats if p.id == c.parent_id), None)
                if parent and parent.name == cat:
                    children.append(c.name)
        
        msg = trf("budget.msg.delete_category_confirm", category=cat) + "\n\n"
        msg += tr("budget.msg.delete_category_warning")
        
        if children:
            msg += "\n\n" + tr("budget.msg.delete_category_also_sub") + "\n"
            msg += "\n".join(f"  • {n}" for n in children[:10])
            if len(children) > 10:
                msg += f"\n  ... und {len(children) - 10} weitere"
        
        if QMessageBox.question(self, tr("budget.title.delete_category"), msg) != QMessageBox.Yes:
            return
        
        self.budget.delete_category_all_years(typ, cat)
        self.cats.delete(typ, cat)
        self.load()
    
    def _copy_row_to_all_months(self, row: int) -> None:
        """Kopiert den ersten Monatswert in alle Monate."""
        cat = self._row_cat_real(row)
        typ = self._row_typ(row)
        if not cat:
            return
        
        # Ersten nicht-leeren Wert finden
        first_val = 0.0
        for m in range(1, 13):
            it = self.table.item(row, m + 3)
            if it and it.text().strip():
                first_val = parse_amount(it.text())
                break
        
        if abs(first_val) < 1e-9:
            QMessageBox.information(
                self, tr("msg.info"),
                tr("budget.msg.no_value_to_copy")
            )
            return
        
        year = int(self.year_spin.value())
        
        for m in range(1, 13):
            self.budget.set_amount(year, m, typ, cat, first_val)
        
        self.load()
        QMessageBox.information(
            self, "OK",
            trf("budget.msg.copied_to_all_months", value=f"{first_val:.2f}")
        )
    
    def _add_favorite(self, typ: str, category: str) -> None:
        """Fügt eine Kategorie zu Favoriten hinzu"""
        self.favorites.add(typ, category)
        self.load()  # Tabelle neu laden um Stern-Symbol anzuzeigen
        QMessageBox.information(
            self, "Favorit",
            trf("budget.msg.added_to_favorites", category=category)
        )
    
    def _remove_favorite(self, typ: str, category: str) -> None:
        """Entfernt eine Kategorie aus Favoriten"""
        self.favorites.remove(typ, category)
        self.load()  # Tabelle neu laden um Stern-Symbol zu entfernen
        QMessageBox.information(
            self, "Favorit",
            f"☆ '{category}' wurde aus Favoriten entfernt."
        )
    
    def _create_auto_warnings(self, year: int) -> None:
        """Erstellt automatisch Budgetwarnungen nur bei tatsächlicher Überschreitung (>100%)"""
        try:
            from model.tracking_model import TrackingModel
            tracking = TrackingModel(self.conn)
            
            for month in range(1, 13):
                for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
                    matrix = self.budget.get_matrix(year, typ)
                    spent_map = tracking.sum_by_category(typ, year=year, month=month)
                    
                    for category, amounts in matrix.items():
                        budget_val = amounts.get(month, 0.0)
                        if budget_val > 0:
                            raw_spent = float(spent_map.get(category, 0.0))
                            spent = raw_spent if is_income(typ) else abs(raw_spent)
                            is_warn = (spent < budget_val) if is_income(typ) else (spent > budget_val)
                            if is_warn:
                                self.warnings.create(year, month, typ, category, threshold_percent=100)
        except Exception as e:
            logger.debug("operation: %s", e)



    # -----------------------------
    # Baum (Ein-/Ausblenden per Zuklappen)

    def _cat_path(self, typ: str, name: str) -> str:
        """Builds a display path like: Root > Child > Leaf (based on parent_id)."""
        try:
            items = self.cats.list(typ)
            by_id = {c.id: c for c in items}
            by_name = {c.name: c for c in items}
            c = by_name.get(name)
            if not c:
                return name
            parts = [c.name]
            guard = 0
            while c.parent_id is not None and guard < 50:
                c = by_id.get(c.parent_id)
                if not c:
                    break
                parts.append(c.name)
                guard += 1
            parts.reverse()
            return " › ".join(parts)
        except Exception:
            return name

    
    def _parent_path_label(self, full_path: str, name: str, depth: int) -> str:
        """Kompakter Label: bei Unterkategorien nur ab Parent anzeigen.

        Beispiel: "Gesundheit › Krankenkasse › Selbstbehalt" -> "Krankenkasse › Selbstbehalt"
        Der volle Pfad bleibt im Tooltip (ROLE_PATH).
        """
        try:
            parts = [p.strip() for p in str(full_path).split("›") if p.strip()]
        except Exception:
            parts = []

        if not parts:
            return name

        # Hauptkategorien: nur eigener Name
        if depth <= 1 or len(parts) == 1:
            return parts[-1]

        # Unterkategorien: Parent + Leaf
        return " › ".join(parts[-2:])



    def _update_tree_labels_all(self) -> None:
        """Refreshes category label column for all data rows."""
        n = self._row_count_data()
        for r in range(n):
            if not self._is_header_row(r) and not self._is_footer_row(r):
                self._update_tree_label_row(r)


    # -----------------------------
    def _format_cat_label(
        self,
        name: str,
        depth: int,
        has_children: bool,
        collapsed: bool,
    ) -> str:
        """Formatiert nur die Bezeichnung (Spalte 0) ohne Fix/Wiederkehrend-Badges.
        
        Diese werden jetzt in separaten Spalten (1-3) angezeigt.
        """
        # In path-mode: Vollständigen Pfad ohne Tree-Marker
        if getattr(self, '_tree_view_mode', 'tree') == 'path':
            return name
        
        # Tree-mode: Einrückung + Marker
        indent = "  " * max(0, int(depth))  # sichtbarer Einzug (Em-Spaces)
        if has_children:
            marker = "▸" if collapsed else "▾"
            parent_marker = f" {tr('budget.parent.marker')}"
        else:
            marker = "•"
            parent_marker = ""

        if depth > 0:
            return f"{indent}{marker} {name}{parent_marker}"
        return f"{marker} {name}{parent_marker}"

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        # Doppelklick auf Kategorie-Spalte toggelt Auf-/Zuklappen
        if col != 0:
            return
        if getattr(self, '_tree_view_mode', 'tree') != 'tree':
            return
        if self._is_header_row(row) or self._is_footer_row(row):
            return
        if not self._row_has_children(row):
            return
        self._toggle_collapse_row(row)

    def _toggle_collapse_row(self, row: int) -> None:
        it0 = self.table.item(row, 0)
        if not it0:
            return
        cur = bool(it0.data(ROLE_COLLAPSED))
        it0.setData(ROLE_COLLAPSED, (not cur))
        self._update_tree_label_row(row)
        self._reapply_tree_visibility()

    def _update_tree_label_row(self, row: int) -> None:
        it0 = self.table.item(row, 0)
        if not it0:
            return

        # Real category name stored in model (needed for flag lookup)
        real_name = self._row_cat_real(row) or it0.text()
        typ = self._row_typ(row)
        depth = self._row_depth(row)

        # Display name depends on view mode
        full_path = it0.data(ROLE_PATH) or self._cat_path(typ, real_name)
        if getattr(self, "_tree_view_mode", "tree") == "path":
            display_name = str(full_path)
        else:
            # Im Baum-Modus reicht der reine Name – Einrückung/Marker zeigen die Hierarchie.
            display_name = str(real_name)

        has_children = self._row_has_children(row)
        collapsed = bool(it0.data(ROLE_COLLAPSED))

        # Flags come from the real category (not the display path)
        is_fix = False
        is_rec = False
        day = 1
        for c in self.cats.list(typ):
            if c.name == real_name:
                is_fix = bool(c.is_fix)
                is_rec = bool(c.is_recurring)
                day = int(c.recurring_day or 1)
                break

        it0.setText(self._format_cat_label(display_name, depth, has_children, collapsed))


    def _show_tree_menu(self) -> None:
        menu = QMenu(self)
        act_expand_all = menu.addAction("Alles aufklappen")
        act_collapse_all = menu.addAction("Alles zuklappen (nur Hauptkategorien)")
        menu.addSeparator()
        act_depth0 = menu.addAction("Nur Ebene 0 anzeigen")
        act_depth1 = menu.addAction("Bis Ebene 1 anzeigen")
        act_depth2 = menu.addAction("Bis Ebene 2 anzeigen")

        menu.addSeparator()
        act_view_tree = menu.addAction("Baum einblenden (Auf/Zuklappen)")
        act_view_path = menu.addAction("Baum ausblenden (Pfad anzeigen)")


        action = menu.exec(self.btn_tree.mapToGlobal(self.btn_tree.rect().bottomLeft()))
        if action is None:
            return

        # View mode toggles
        if action == act_view_tree:
            self._tree_view_mode = 'tree'
            self._update_tree_labels_all()
            self._reapply_tree_visibility()
            return
        if action == act_view_path:
            self._tree_view_mode = 'path'
            # In path mode we show everything (no collapsing)
            self._set_visible_depth(None)
            self._update_tree_labels_all()
            return

        if action == act_expand_all:
            self._set_visible_depth(None)
        elif action == act_collapse_all or action == act_depth0:
            self._set_visible_depth(0)
        elif action == act_depth1:
            self._set_visible_depth(1)
        elif action == act_depth2:
            self._set_visible_depth(2)

    def _set_visible_depth(self, max_depth: int | None) -> None:
        """Steuert das Baum-Ein-/Ausblenden.

        max_depth=None  -> alles sichtbar (keine Collapses)
        max_depth=0     -> nur Ebene 0 sichtbar (Root-Kategorien)
        max_depth=1/2   -> bis zu dieser Ebene sichtbar, darunter zugeklappt
        """
        data_rows = self._row_count_data()
        for r in range(data_rows):
            if self._is_header_row(r) or self._is_footer_row(r):
                continue
            if not self._row_cat_real(r):
                continue

            it0 = self.table.item(r, 0)
            if not it0:
                continue

            depth = self._row_depth(r)
            has_children = self._row_has_children(r)
            if not has_children:
                continue

            if max_depth is None:
                it0.setData(ROLE_COLLAPSED, False)
            else:
                it0.setData(ROLE_COLLAPSED, bool(depth >= max_depth))

            self._update_tree_label_row(r)

        self._reapply_tree_visibility()

    def _reapply_tree_visibility(self) -> None:
        """Setzt RowHidden basierend auf collapse-Flags neu (robust bei verschachtelten Collapses)."""
        data_rows = self._row_count_data()
        collapsed_depth_stack: list[int] = []

        for r in range(data_rows):
            if self._is_header_row(r):
                collapsed_depth_stack.clear()
                self.table.setRowHidden(r, False)
                continue

            cat = self._row_cat_real(r)
            if not cat:
                self.table.setRowHidden(r, False)
                continue

            depth = self._row_depth(r)

            while collapsed_depth_stack and depth <= collapsed_depth_stack[-1]:
                collapsed_depth_stack.pop()

            hidden = bool(collapsed_depth_stack)
            self.table.setRowHidden(r, hidden)

            if (not hidden) and self._row_has_children(r):
                it0 = self.table.item(r, 0)
                if it0 and bool(it0.data(ROLE_COLLAPSED)):
                    collapsed_depth_stack.append(depth)

    # -----------------------------
    # Übersicht + Styling (Budget-Tab)
    # -----------------------------
    def _apply_table_styles(self) -> None:
        """Einheitliches Styling für Header/Parent/TOTAL + bessere Übersicht."""
        pal = self.table.palette()
        alt = pal.color(QPalette.AlternateBase)

        header_bg = alt.lighter(112)
        parent_bg = alt.lighter(108)
        total_bg = alt.lighter(120)

        data_rows = self._row_count_data()
        for r in range(self.table.rowCount()):
            if self._is_footer_row(r):
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it:
                        it.setBackground(QBrush(total_bg))
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                continue

            if r < data_rows and self._is_header_row(r):
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it:
                        it.setBackground(QBrush(header_bg))
                continue

            if r < data_rows and self._row_has_children(r):
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it:
                        it.setBackground(QBrush(parent_bg))
                        if c == 0:
                            f = it.font()
                            f.setBold(True)
                            it.setFont(f)


            # Hauptkategorien (Depth 0) immer fett – auch wenn keine Kinder vorhanden
            if r < data_rows and (not self._is_header_row(r)) and (not self._is_footer_row(r)):
                try:
                    if self._row_depth(r) == 0:
                        it0 = self.table.item(r, 0)
                        if it0:
                            f = it0.font()
                            f.setBold(True)
                            it0.setFont(f)
                except Exception as e:
                    logger.debug("if self._row_depth(r) == 0:: %s", e)

    def _compute_totals_by_typ(self) -> dict[str, dict[int, float]]:
        """Berechnet Monats- und Jahres-Totals je Typ (nutzt Parent-Puffer zur Vermeidung von Doppelzählung)."""
        selected = self._current_typ_db()
        types = [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS] if selected == "Alle" else [selected]

        totals: dict[str, dict[int, float]] = {t: {m: 0.0 for m in range(1, 14)} for t in types}

        data_rows = self._row_count_data()
        for r in range(data_rows):
            if self._is_header_row(r):
                continue
            cat = self._row_cat_real(r)
            if not cat:
                continue
            t = self._row_typ(r)
            if t not in totals:
                continue
            has_children = self._row_has_children(r)

            for m in range(1, 13):
                if has_children:
                    totals[t][m] += float(self._buffer_cache.get((t, cat), {}).get(m, 0.0))
                else:
                    # Spalten: 0=Bezeichnung, 1=Fix, 2=∞, 3=Tag, 4-15=Monate, 16=Total
                    # Monat m (1-12) entspricht Spalte m+3 (4-15)
                    it = self.table.item(r, m + 3)
                    totals[t][m] += parse_amount(it.text() if it else "")

        for t in types:
            totals[t][13] = sum(totals[t][m] for m in range(1, 13))

        return totals

    def _update_overview_bar(self) -> None:
        year = int(self.year_spin.value())
        selected = self._current_typ_db()
        totals = self._compute_totals_by_typ()

        if selected != "Alle":
            grand = totals.get(selected, {}).get(13, 0.0)
            avg = grand / 12.0
            self.lbl_overview.setText(trf("budget.overview.single", typ=display_typ(selected), year=year, year_budget=fmt_amount(grand), month_avg=fmt_amount(avg)))
        else:
            parts = []
            for t in [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]:
                g = totals.get(t, {}).get(13, 0.0)
                parts.append(trf("budget.overview.part", typ=display_typ(t), value=fmt_amount(g)))
            self.lbl_overview.setText(trf("budget.overview.all", year=year, parts="  •  ".join(parts)))
