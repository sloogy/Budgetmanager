from __future__ import annotations
import sqlite3

from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    QMenu, QInputDialog
)

from model.category_model import CategoryModel, Category
from model.budget_model import BudgetModel
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

MONTHS = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

# UserRole keys
ROLE_CAT_REAL = Qt.UserRole + 1     # str
ROLE_DEPTH = Qt.UserRole + 2        # int
ROLE_HAS_CHILDREN = Qt.UserRole + 3 # bool
ROLE_PATH = Qt.UserRole + 4         # str
ROLE_COLLAPSED = Qt.UserRole + 5     # bool (für Baum-Zuklappen)
ROLE_TYP = Qt.UserRole + 10         # str (bereits im alten Code genutzt)


def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF", "").strip()
    s = s.replace("'", "").replace(" ", "").replace(",", ".")
    return float(s)


def fmt_amount(val: float) -> str:
    if abs(val) < 1e-9:
        return ""
    return f"{val:.2f}"


class BudgetTab(QWidget):
    """Budget-Tab mit Tree-Ansicht.

    Regeln:
    - Leaf-Kategorien: editierbar (Monate + Total)
    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
      Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
    - Parent ohne Children: wie Leaf (normales Budgetverhalten)

    Footer (TOTAL): zählt **Leaf-Werte + Parent-Puffer** (keine Doppelzählung).
    """
    
    # Signal für Schnelleingabe (wird von MainWindow abgehört)
    quick_add_requested = Signal()

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.cats = CategoryModel(conn)
        self.budget = BudgetModel(conn)

        self._internal_change = False

        # Cache: (typ, cat) -> {month:int -> buffer(float)}
        self._buffer_cache: dict[tuple[str, str], dict[int, float]] = {}

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(2024)

        self.typ_cb = QComboBox()
        self.typ_cb.addItems(["Alle", "Ausgaben", "Einkommen", "Ersparnisse"])

        # Baum-Ansicht (Ein-/Ausblenden / Ebenen)
        self.btn_tree = QPushButton("🌳 Baum")
        self.btn_tree.setToolTip("Baum-Ansicht steuern (Ein-/Ausblenden, Ebenen, Auf-/Zuklappen)")

        # Baum-Ansicht: 'tree' (Einrueckung/Marker) oder 'path' (Pfadtext)
        self._tree_view_mode = 'tree'


        self.btn_load = QPushButton("Laden")
        self.btn_save = QPushButton("Speichern")
        self.btn_seed = QPushButton("Zeilen aus Kategorien erzeugen")
        self.btn_copy = QPushButton("Jahr kopieren…")

        self.btn_entry = QPushButton("Budget erfassen…")
        self.btn_edit = QPushButton("Budget bearbeiten…")
        
        # Schnelleingabe-Button
        self.btn_quick_add = QPushButton("⚡ Schnelleingabe")
        self.btn_quick_add.setToolTip("Schnell einen neuen Tracking-Eintrag erfassen (Ctrl+N)")

        self.btn_remove_budgetrow = QPushButton("Budget-Zeile entfernen")
        self.btn_remove_category = QPushButton("Kategorie löschen (global)")

        self.chk_autosave = QCheckBox("Auto-Speichern")
        self.chk_autosave.setChecked(False)

        self.chk_ask_due = QCheckBox("Beim Tippen nach Fälligkeit fragen")
        self.chk_ask_due.setChecked(True)

        # Kleine Übersicht (oberhalb der Tabelle)
        self.lbl_overview = QLabel("")
        self.lbl_overview.setToolTip(
            "Schnellübersicht zum aktuell gewählten Jahr/Typ (Jahrestotal und Monatsdurchschnitt)."
        )

        # Kategorie + 12 Monate + Total
        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(["Kategorie"] + MONTHS + ["Total"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)

        # Events
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.installEventFilter(self)
        
        # Rechtsklick-Kontextmenü
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Shortcuts
        self.sc_save = QShortcut(QKeySequence.Save, self)
        self.sc_save.activated.connect(self.save)

        # Kompakte Top-Leiste
        top = QHBoxLayout()
        top.addWidget(QLabel("Jahr"))
        top.addWidget(self.year_spin)
        top.addWidget(QLabel("Typ"))
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

    # --- Komfort: Enter -> nächste Zelle ---
    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r < 0 or c < 0:
                    return False
                if c == 0:
                    self.table.setCurrentCell(r, 1)
                else:
                    next_c = c + 1
                    next_r = r
                    if next_c >= 14:  # after Total -> next row
                        next_c = 1
                        next_r = r + 1
                    if next_r >= self.table.rowCount():
                        next_r = self.table.rowCount() - 1
                    self.table.setCurrentCell(next_r, next_c if next_c != 13 else 13)
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
        cur = self.typ_cb.currentText()
        return "Ausgaben" if cur == "Alle" else cur

    def _row_cat_real(self, r: int) -> str | None:
        it0 = self.table.item(r, 0)
        if not it0:
            return None
        v = it0.data(ROLE_CAT_REAL)
        if v:
            return str(v)
        # fallback: avoid header/footer
        txt = (it0.text() or "").strip()
        if not txt or txt in ("TOTAL",):
            return None
        if txt.startswith("═══"):
            return None
        return txt

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
        return flat, totals_by_name, buffer_by_name

    def seed_from_categories(self):
        year = int(self.year_spin.value())
        typ = self.typ_cb.currentText()
        if typ == "Alle":
            types = ["Ausgaben", "Einkommen", "Ersparnisse"]
        else:
            types = [typ]

        for t in types:
            names = self.cats.list_names(t)
            self.budget.seed_year_from_categories(year, t, names, amount=0.0)

        QMessageBox.information(self, "OK", f"Budget-Zeilen für {typ} {year} erzeugt.")
        self.load()

    def load(self):
        year = int(self.year_spin.value())
        typ = self.typ_cb.currentText()

        if typ == "Alle":
            types = ["Ausgaben", "Einkommen", "Ersparnisse"]
        else:
            types = [typ]

        self._buffer_cache.clear()

        self._internal_change = True
        try:
            self.table.setRowCount(0)

            for t in types:
                matrix = self.budget.get_matrix(year, t)
                flat, totals_by_name, buffer_by_name = self._build_tree_flat(t, matrix)

                # Buffer cache (für Footer + Parent-Puffer)
                for name, own in buffer_by_name.items():
                    self._buffer_cache[(t, name)] = dict(own)

                # Typ-Header, wenn "Alle"
                if typ == "Alle" and flat:
                    r = self.table.rowCount()
                    self.table.insertRow(r)
                    header_item = QTableWidgetItem(f"═══ {t} ═══")
                    header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
                    font = header_item.font()
                    font.setBold(True)
                    header_item.setFont(font)
                    header_item.setData(ROLE_TYP, t)
                    self.table.setItem(r, 0, header_item)
                    for m in range(1, 14):
                        empty = QTableWidgetItem("")
                        empty.setFlags(empty.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(r, m, empty)

                for row in flat:
                    name = row["name"]
                    depth = int(row["depth"])
                    has_children = bool(row["has_children"])
                    path = str(row["path"])

                    r = self.table.rowCount()
                    self.table.insertRow(r)

                    collapsed = False
                    label = self._format_cat_label(name, depth, has_children, collapsed, row.get("is_fix", False), row.get("is_recurring", False), row.get("recurring_day", 1))
                    cat_item = QTableWidgetItem(label)
                    cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
                    cat_item.setData(ROLE_TYP, t)
                    cat_item.setData(ROLE_CAT_REAL, name)
                    cat_item.setData(ROLE_DEPTH, depth)
                    cat_item.setData(ROLE_HAS_CHILDREN, has_children)
                    cat_item.setData(ROLE_PATH, path)
                    cat_item.setData(ROLE_COLLAPSED, False)
                    cat_item.setToolTip(path)
                    self.table.setItem(r, 0, cat_item)

                    row_total = 0.0
                    for m in range(1, 13):
                        total_val = float(totals_by_name.get(name, {}).get(m, 0.0))
                        own_val = float(buffer_by_name.get(name, {}).get(m, 0.0))
                        child_val = float(total_val - own_val)

                        it = QTableWidgetItem(fmt_amount(total_val))
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        it.setData(ROLE_TYP, t)

                        # Leaf ODER Parent ohne Children -> normal editierbar
                        # Parent mit Children -> editierbar als Puffer (Monat), Anzeige bleibt Total
                        if has_children:
                            # Monatszellen editierbar, aber Total-Spalte später read-only
                            it.setToolTip(
                                f"Total: {fmt_amount(total_val)}\n"
                                f"Puffer (Eigenbetrag): {fmt_amount(own_val)}\n"
                                f"Kinder: {fmt_amount(child_val)}"
                            )
                        else:
                            it.setToolTip(path)

                        self.table.setItem(r, m, it)
                        row_total += total_val

                    tot = QTableWidgetItem(fmt_amount(row_total))
                    tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    tot.setToolTip(path)

                    # Total-Spalte: Parent mit Children -> read-only (weil sonst unlogisch)
                    if has_children:
                        tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
                        tot.setToolTip(
                            "Total ist bei Parent-Kategorien read-only.\n"
                            "Ändere den Eigenbetrag (Puffer) in den Monatszellen."
                        )
                    self.table.setItem(r, 13, tot)

            self._recalc_footer()
            self._reapply_tree_visibility()
            self.table.resizeColumnsToContents()
        finally:
            self._internal_change = False

    # -----------------------------
    # Parent recalculation helpers
    # -----------------------------
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
                total += parse_amount(it.text() if it else "")
            i += 1
        return total

    def _update_parent_chain(self, start_row: int, month_col: int):
        """Rechnet für diesen Monat alle Parent-Zeilen nach oben neu."""
        data_rows = self._row_count_data()
        if start_row >= data_rows:
            return

        cur_row = start_row
        cur_depth = self._row_depth(cur_row)
        if cur_depth <= 0:
            return

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

            buf = float(self._buffer_cache.get((typ, cat), {}).get(month_col, 0.0))
            children_sum = self._sum_immediate_children_month(parent_row, month_col)
            new_total = buf + children_sum

            # Update cell
            it = self.table.item(parent_row, month_col)
            if it is None:
                it = QTableWidgetItem()
                self.table.setItem(parent_row, month_col, it)
            self._internal_change = True
            try:
                it.setText(fmt_amount(new_total))
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # Tooltip aktualisieren
                it.setToolTip(
                    f"Total: {fmt_amount(new_total)}\n"
                    f"Puffer (Eigenbetrag): {fmt_amount(buf)}\n"
                    f"Kinder: {fmt_amount(children_sum)}"
                )
            finally:
                self._internal_change = False

            self._recalc_row_total(parent_row)

            # Weiter nach oben
            cur_row = parent_row
            cur_depth -= 1

    # -----------------------------
    # Footer / totals
    # -----------------------------
    def _recalc_footer(self):
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
                    it = self.table.item(r, m)
                    col_sum += parse_amount(it.text() if it else "")

            grand += col_sum
            cell = QTableWidgetItem(fmt_amount(col_sum))
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(footer, m, cell)

        gcell = QTableWidgetItem(fmt_amount(grand))
        gcell.setFlags(gcell.flags() & ~Qt.ItemIsEditable)
        gcell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(footer, 13, gcell)

        # Styling + Übersicht aktualisieren (damit TOTAL/Parent/Headers sauber bleiben)
        self._apply_table_styles()
        self._update_overview_bar()

    def _persist_single_cell(self, r: int, month_col: int):
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

        if typ == "Ausgaben" and amt < 0:
            amt = abs(amt)
        self.budget.set_amount(year, month_col, typ, cat, amt)

    def _get_db_value(self, typ: str, cat: str, month: int) -> float:
        year = int(self.year_spin.value())
        mat = self.budget.get_matrix(year, typ)
        return float(mat.get(cat, {}).get(month, 0.0))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._internal_change:
            return

        r = item.row()
        c = item.column()

        # ignore footer row
        if self._is_footer_row(r):
            return
        # ignore header rows
        if self._is_header_row(r):
            return
        # ignore category edits
        if c == 0:
            return

        typ = self._row_typ(r)
        cat = self._row_cat_real(r)
        if not cat:
            return

        has_children = self._row_has_children(r)

        # Parent + Children: Total-Spalte ist read-only (sollte nicht editierbar sein)
        if has_children and c == 13:
            self._internal_change = True
            try:
                # restore displayed value
                # We recompute from month cells
                pass
            finally:
                self._internal_change = False
            return

        # Feature #1: if user edits Total -> distribute across months (nur Leaf/Parent ohne Children)
        if c == 13 and not has_children:
            try:
                total = parse_amount(item.text())
            except Exception:
                total = 0.0
            if typ == "Ausgaben" and total < 0:
                total = abs(total)
                QMessageBox.information(self, "Hinweis", "Bei Ausgaben sind negative Beträge nicht erlaubt – Wert wurde korrigiert.")

            base = round(total / 12.0, 2)
            last = round(total - base * 11, 2)

            self._internal_change = True
            try:
                for m in range(1, 12):
                    it = self.table.item(r, m)
                    if it is None:
                        it = QTableWidgetItem()
                        self.table.setItem(r, m, it)
                    it.setText(fmt_amount(base))
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it12 = self.table.item(r, 12)
                if it12 is None:
                    it12 = QTableWidgetItem()
                    self.table.setItem(r, 12, it12)
                it12.setText(fmt_amount(last))
                it12.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setText(fmt_amount(total))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            finally:
                self._internal_change = False

            self._recalc_row_total(r)
            # parents updaten (alle Monate)
            for m in range(1, 13):
                self._update_parent_chain(r, m)
            self._recalc_footer()

            if self.chk_autosave.isChecked():
                for m in range(1, 13):
                    self._persist_single_cell(r, m)
            return

        # month cell edit: c in 1..12
        if 1 <= c <= 12:
            # Parent: edit interpretiert als Puffer
            if has_children:
                try:
                    typed = parse_amount(item.text())
                except Exception:
                    typed = 0.0
                if typ == "Ausgaben" and typed < 0:
                    typed = abs(typed)
                    QMessageBox.information(self, "Hinweis", "Bei Ausgaben sind negative Beträge nicht erlaubt – Wert wurde korrigiert.")

                # Persist buffer sofort
                year = int(self.year_spin.value())
                self.budget.set_amount(year, c, typ, cat, typed)
                self._buffer_cache.setdefault((typ, cat), {})[c] = float(typed)

                # Display = buffer + children sum
                children_sum = self._sum_immediate_children_month(r, c)
                display = float(typed) + float(children_sum)

                self._internal_change = True
                try:
                    item.setText(fmt_amount(display))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setToolTip(
                        f"Total: {fmt_amount(display)}\n"
                        f"Puffer (Eigenbetrag): {fmt_amount(typed)}\n"
                        f"Kinder: {fmt_amount(children_sum)}"
                    )
                finally:
                    self._internal_change = False

                self._recalc_row_total(r)
                self._update_parent_chain(r, c)
                self._recalc_footer()
                return

            # Leaf: optional "ask due" dialog
            if self.chk_ask_due.isChecked():
                try:
                    typed = parse_amount(item.text())
                except Exception:
                    typed = 0.0
                if typ == "Ausgaben" and typed < 0:
                    typed = abs(typed)

                # revert to previous db value first (so cancel doesn't keep typed value)
                prev = self._get_db_value(typ, cat, c)
                self._internal_change = True
                try:
                    item.setText(fmt_amount(prev))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                finally:
                    self._internal_change = False

                _, is_rec, _day = self.cats.get_flags(typ, cat)
                default_mode = "Alle" if is_rec else "Monat"
                dlg = BudgetEntryDialog(
                    self,
                    default_year=int(self.year_spin.value()),
                    default_typ=typ,
                    categories=(self.cats.list_names_tree(typ) if hasattr(self.cats, "list_names_tree") else self.cats.list_names(typ)),
                    preset={"category": cat, "amount": typed, "month": c, "mode": default_mode, "only_if_empty": False},
                )
                if dlg.exec() == QDialog.Accepted:
                    self._apply_request(dlg.get_request())
                return

        # Normal direct edit: normalize + totals + optional autosave (Leaf/Parent ohne Children)
        try:
            val = parse_amount(item.text())
        except Exception:
            val = 0.0

        if typ == "Ausgaben" and val < 0:
            val = abs(val)
            QMessageBox.information(self, "Hinweis", "Bei Ausgaben sind negative Beträge nicht erlaubt – Wert wurde korrigiert.")

        self._internal_change = True
        try:
            item.setText(fmt_amount(val))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = False

        self._recalc_row_total(r)
        if 1 <= c <= 12:
            self._update_parent_chain(r, c)
        self._recalc_footer()

        if self.chk_autosave.isChecked() and (1 <= c <= 12):
            self._persist_single_cell(r, c)

    def _recalc_row_total(self, r: int):
        data_rows = self._row_count_data()
        if r >= data_rows:
            return
        if self._is_header_row(r):
            return
        row_total = 0.0
        for m in range(1, 13):
            it = self.table.item(r, m)
            row_total += parse_amount(it.text() if it else "")
        tot = self.table.item(r, 13)
        if tot is None:
            tot = QTableWidgetItem()
            self.table.setItem(r, 13, tot)
        self._internal_change = True
        try:
            tot.setText(fmt_amount(row_total))
            tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = False

    def save(self):
        year = int(self.year_spin.value())
        data_rows = self._row_count_data()

        for r in range(data_rows):
            if self._is_header_row(r):
                continue
            cat = self._row_cat_real(r)
            if not cat:
                continue
            typ = self._row_typ(r)
            has_children = self._row_has_children(r)

            # Parent mit Children: Monatszellen zeigen Total, speichern wäre falsch.
            # Buffer wurde beim Edit sofort gespeichert.
            if has_children:
                continue

            for m in range(1, 13):
                it = self.table.item(r, m)
                amt = parse_amount(it.text() if it else "")
                if typ == "Ausgaben" and amt < 0:
                    amt = abs(amt)
                self.budget.set_amount(year, m, typ, cat, amt)
            self._recalc_row_total(r)

        self._recalc_footer()
        QMessageBox.information(self, "OK", "Budget gespeichert. (Tipp: Strg+S funktioniert auch)")

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
                    self, "Kategorie-Fehler", 
                    f"Konnte Kategorie '{req.category}' nicht erstellen:\n{e}"
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
            amt = abs(req.amount) if (req.typ == "Ausgaben" and req.amount < 0) else req.amount

            if req.only_if_empty:
                mat = self.budget.get_matrix(req.year, req.typ)
                current = mat.get(req.category, {}).get(m, 0.0)
                if abs(float(current)) > 1e-9:
                    continue

            self.budget.set_amount(req.year, m, req.typ, req.category, amt)

        self.year_spin.setValue(req.year)
        self.typ_cb.setCurrentText(req.typ)
        self.load()
        self._focus_category_month(req.category, months[0])

    def _focus_category_month(self, category: str, month: int):
        data_rows = self._row_count_data()
        for r in range(data_rows):
            if self._is_header_row(r):
                continue
            it = self.table.item(r, 0)
            if it and it.data(ROLE_CAT_REAL) == category:
                col = max(1, min(12, month))
                self.table.setCurrentCell(r, col)
                return

    def open_entry_dialog(self):
        year = int(self.year_spin.value())

        # wenn "Alle": versuche typ vom aktuell selektierten Row zu nehmen
        r = self.table.currentRow()
        if r >= 0 and r < self._row_count_data() and not self._is_header_row(r):
            typ = self._row_typ(r)
            cat = self._row_cat_real(r)
        else:
            cur = self.typ_cb.currentText()
            typ = "Ausgaben" if cur == "Alle" else cur
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
        if r < 0 or c < 1 or c > 12:
            QMessageBox.information(self, "Hinweis", "Bitte eine Monatszelle (Jan–Dez) auswählen, die du bearbeiten willst.")
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
                "Hinweis",
                "Diese Kategorie hat Unterkategorien.\n\n"
                "Die Monatswerte sind die Summe (Kinder + Puffer).\n"
                "Ändere den Puffer direkt in der Monatszelle (Zahl eingeben).",
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
            preset={"category": cat, "amount": current_val, "month": c, "mode": default_mode, "only_if_empty": False},
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
            QMessageBox.information(self, "Hinweis", "Bitte eine Kategorie-Zeile auswählen (nicht TOTAL/Header).")
            return
        typ, cat = sel
        year = int(self.year_spin.value())

        if QMessageBox.question(
            self,
            "Budget-Zeile entfernen",
            f"Soll die Budget-Zeile '{cat}' für {typ} im Jahr {year} gelöscht werden?",
        ) != QMessageBox.Yes:
            return

        self.budget.delete_category_for_year(year, typ, cat)
        self.load()

    def delete_category_global(self):
        sel = self._selected_category()
        if not sel:
            QMessageBox.information(self, "Hinweis", "Bitte eine Kategorie-Zeile auswählen (nicht TOTAL/Header).")
            return
        typ, cat = sel

        msg = (
            "ACHTUNG: Das entfernt die Kategorie GLOBAL aus der Kategorien-Liste und löscht alle Budget-Einträge "
            f"für '{cat}' ({typ}) in ALLEN Jahren.\n\nFortfahren?"
        )

        if QMessageBox.question(self, "Kategorie löschen", msg) != QMessageBox.Yes:
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
            QMessageBox.warning(self, "Fehler", "Quelljahr und Zieljahr müssen verschieden sein.")
            return

        typ = None if req.scope_typ == "Alle" else req.scope_typ
        self.budget.copy_year(req.src_year, req.dst_year, carry_amounts=req.carry_amounts, typ=typ)

        if typ is None:
            for t in ["Ausgaben", "Einkommen", "Ersparnisse"]:
                self.budget.seed_year_from_categories(req.dst_year, t, self.cats.list_names(t), amount=0.0)
        else:
            self.budget.seed_year_from_categories(req.dst_year, typ, self.cats.list_names(typ), amount=0.0)

        QMessageBox.information(self, "OK", f"Budget {req.src_year} → {req.dst_year} kopiert.")
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
        menu.addSection(f"📁 Kategorie: {cat}")
        
        act_props = menu.addAction("⚙️ Eigenschaften bearbeiten...")
        act_rename = menu.addAction("✏️ Umbenennen...")
        
        menu.addSeparator()
        
        # Flags-Toggle (direkt umschaltbar)
        if cat_obj:
            fix_text = "✓ Fixkosten deaktivieren" if cat_obj.is_fix else "☐ Fixkosten aktivieren"
            act_toggle_fix = menu.addAction(fix_text)
            
            rec_text = "✓ Wiederkehrend deaktivieren" if cat_obj.is_recurring else "☐ Wiederkehrend aktivieren"
            act_toggle_rec = menu.addAction(rec_text)
            
            act_set_day = menu.addAction(f"📅 Fälligkeitstag setzen... (aktuell: {cat_obj.recurring_day}.)")
        else:
            act_toggle_fix = None
            act_toggle_rec = None
            act_set_day = None
        
        menu.addSeparator()
        
        act_new = menu.addAction("➕ Neue Kategorie erstellen...")
        act_new_sub = menu.addAction("📂 Neue Unterkategorie hier...")
        
        menu.addSeparator()
        
        act_delete_budget = menu.addAction("🗑️ Budget-Zeile entfernen (nur dieses Jahr)")
        act_delete_cat = menu.addAction("⚠️ Kategorie komplett löschen...")
        
        menu.addSeparator()
        
        # === Budget-Aktionen ===
        menu.addSection("💰 Budget")
        
        act_edit = menu.addAction("Budget bearbeiten...")
        act_copy_row = menu.addAction("Zeile in alle Monate kopieren")
        
        # Aktion ausführen
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action is None:
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
            self, "Kategorie umbenennen",
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
                self, "Fehler",
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
                self, "OK",
                f"Kategorie umbenannt: '{cat_name}' → '{new_name}'"
            )
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Umbenennen fehlgeschlagen:\n{e}")
    
    def _toggle_category_fix(self, cat: Category) -> None:
        """Schaltet Fixkosten-Flag um."""
        try:
            new_val = not cat.is_fix
            self.cats.update_flags(cat.id, is_fix=new_val)
            status = "aktiviert" if new_val else "deaktiviert"
            QMessageBox.information(self, "OK", f"Fixkosten für '{cat.name}' {status}.")
            self.load()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
    def _toggle_category_recurring(self, cat: Category) -> None:
        """Schaltet Wiederkehrend-Flag um."""
        try:
            new_val = not cat.is_recurring
            self.cats.update_flags(cat.id, is_recurring=new_val)
            status = "aktiviert" if new_val else "deaktiviert"
            QMessageBox.information(self, "OK", f"Wiederkehrend für '{cat.name}' {status}.")
            self.load()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
    def _set_category_day(self, cat: Category) -> None:
        """Setzt den Fälligkeitstag."""
        day, ok = QInputDialog.getInt(
            self, "Fälligkeitstag setzen",
            f"Tag im Monat für '{cat.name}' (1-31):",
            cat.recurring_day, 1, 31
        )
        if not ok:
            return
        
        try:
            self.cats.update_flags(cat.id, is_recurring=True, recurring_day=day)
            QMessageBox.information(
                self, "OK",
                f"Fälligkeitstag für '{cat.name}' auf {day}. gesetzt."
            )
            self.load()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
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
            self, "Neue Unterkategorie",
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
            QMessageBox.critical(self, "Fehler", f"Erstellen fehlgeschlagen:\n{e}")
    
    def _delete_budget_row_for_category(self, cat: str, typ: str) -> None:
        """Löscht nur die Budget-Zeile für dieses Jahr."""
        year = int(self.year_spin.value())
        
        if QMessageBox.question(
            self,
            "Budget-Zeile entfernen",
            f"Budget-Zeile für '{cat}' im Jahr {year} entfernen?\n\n"
            "Die Kategorie bleibt erhalten, nur die Budget-Werte werden gelöscht."
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
        
        msg = f"Kategorie '{cat}' komplett löschen?\n\n"
        msg += "⚠️ WARNUNG: Dies löscht auch alle Budget-Einträge in ALLEN Jahren!"
        
        if children:
            msg += f"\n\nFolgende Unterkategorien werden ebenfalls gelöscht:\n"
            msg += "\n".join(f"  • {n}" for n in children[:10])
            if len(children) > 10:
                msg += f"\n  ... und {len(children) - 10} weitere"
        
        if QMessageBox.question(self, "Kategorie löschen", msg) != QMessageBox.Yes:
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
            it = self.table.item(row, m)
            if it and it.text().strip():
                first_val = parse_amount(it.text())
                break
        
        if abs(first_val) < 1e-9:
            QMessageBox.information(
                self, "Hinweis",
                "Kein Wert zum Kopieren gefunden. Bitte erst einen Monat ausfüllen."
            )
            return
        
        year = int(self.year_spin.value())
        
        for m in range(1, 13):
            self.budget.set_amount(year, m, typ, cat, first_val)
        
        self.load()
        QMessageBox.information(
            self, "OK",
            f"Wert {first_val:.2f} in alle 12 Monate übernommen."
        )



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
        is_fix: bool = False,
        is_recurring: bool = False,
        recurring_day: int = 1,
    ) -> str:
        indent = "  " * max(0, int(depth))
        if has_children:
            marker = "▸" if collapsed else "▾"
        else:
            marker = "•"

        badges = []
        if is_fix:
            badges.append("🧾")
        if is_recurring:
            badges.append(f"🔁{int(recurring_day)}.")
        badge_txt = (" " + " ".join(badges)) if badges else ""

        # In path-mode we show the full category path and hide tree markers/indent.
        if getattr(self, '_tree_view_mode', 'tree') == 'path':
            return f"{name}{badge_txt}"


        if depth > 0:
            return f"{indent}{marker} {name}{badge_txt}"
        return f"{marker} {name}{badge_txt}"

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

        # Display name depends on view mode
        display_name = real_name
        if getattr(self, "_tree_view_mode", "tree") == "path":
            display_name = self._cat_path(typ, real_name)

        depth = self._row_depth(row)
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

        it0.setText(self._format_cat_label(display_name, depth, has_children, collapsed, is_fix, is_rec, day))


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

    def _compute_totals_by_typ(self) -> dict[str, dict[int, float]]:
        """Berechnet Monats- und Jahres-Totals je Typ (nutzt Parent-Puffer zur Vermeidung von Doppelzählung)."""
        selected = self.typ_cb.currentText()
        types = ["Ausgaben", "Einkommen", "Ersparnisse"] if selected == "Alle" else [selected]

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
                    it = self.table.item(r, m)
                    totals[t][m] += parse_amount(it.text() if it else "")

        for t in types:
            totals[t][13] = sum(totals[t][m] for m in range(1, 13))

        return totals

    def _update_overview_bar(self) -> None:
        year = int(self.year_spin.value())
        selected = self.typ_cb.currentText()
        totals = self._compute_totals_by_typ()

        if selected != "Alle":
            grand = totals.get(selected, {}).get(13, 0.0)
            avg = grand / 12.0
            self.lbl_overview.setText(
                f"Übersicht: {selected} {year}  |  Jahresbudget: {fmt_amount(grand)}  |  Monat Ø: {fmt_amount(avg)}"
            )
        else:
            parts = []
            for t in ["Einkommen", "Ausgaben", "Ersparnisse"]:
                g = totals.get(t, {}).get(13, 0.0)
                parts.append(f"{t}: {fmt_amount(g)}")
            self.lbl_overview.setText(f"Übersicht: {year}  |  " + "  •  ".join(parts))
